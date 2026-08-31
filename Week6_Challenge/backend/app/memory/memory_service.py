import json
import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.memory import Memory, MemoryType
from app.models.trace import TraceStatus, TraceType
from app.services.llm_service import LLMError, default_model_for_provider, generate_reply
from app.services.trace_service import record_trace, timed_span
from app.services.usage_service import estimate_cost_breakdown, record_usage

logger = logging.getLogger("app.memory")

_EXTRACTION_SYSTEM_PROMPT = (
    "You extract durable facts worth remembering about a user from one chat exchange: "
    "stated preferences, recurring topics, or facts they'd want recalled later. "
    "Reply with ONLY a JSON array of up to 3 objects shaped like "
    '{"key": "short_slug", "value": "the fact, phrased plainly"}. '
    "If nothing durable was said, reply with an empty JSON array: []"
)


def get_context_memories(workspace_id: str, user_id: str, db: Session, limit: int | None = None) -> list[Memory]:
    settings = get_settings()
    limit = limit or settings.memory_context_limit

    query = (
        db.query(Memory)
        .filter(Memory.workspace_id == workspace_id)
        .filter(or_(Memory.user_id == user_id, Memory.user_id.is_(None)))
        .order_by(Memory.pinned.desc(), Memory.updated_at.desc())
        .limit(limit)
    )
    return query.all()


def format_memories_for_prompt(memories: list[Memory]) -> str:
    if not memories:
        return ""
    lines = [f"- {memory.value}" for memory in memories]
    return "Known context about this user (from memory):\n" + "\n".join(lines)


def upsert_memory(
    workspace_id: str,
    user_id: str,
    key: str,
    value: str,
    db: Session,
    memory_type: MemoryType = MemoryType.LONG_TERM,
    pinned: bool = False,
    conversation_id: str | None = None,
) -> Memory:
    existing = (
        db.query(Memory)
        .filter(Memory.workspace_id == workspace_id, Memory.user_id == user_id, Memory.key == key)
        .first()
    )
    if existing is not None:
        existing.value = value
        existing.memory_type = memory_type
        if pinned:
            existing.pinned = True
        db.commit()
        db.refresh(existing)
        return existing

    memory = Memory(
        workspace_id=workspace_id,
        user_id=user_id,
        conversation_id=conversation_id,
        memory_type=memory_type,
        key=key,
        value=value,
        pinned=pinned,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def extract_and_store_memories(
    workspace_id: str, user_id: str, conversation_id: str, user_message: str, assistant_message: str, db: Session
) -> None:
    """Best-effort extraction. Never raises — a failure here must not break the
    chat turn that triggered it; instead it's recorded as a degraded trace so
    it's visible on the dashboard rather than silently swallowed."""
    settings = get_settings()
    default_model = default_model_for_provider(settings.llm_provider)
    trace_status = TraceStatus.SUCCESS
    trace_error: str | None = None
    input_tokens = output_tokens = 0

    with timed_span() as span:
        try:
            exchange = f"User: {user_message}\nAssistant: {assistant_message}"
            result = generate_reply(
                system_prompt=_EXTRACTION_SYSTEM_PROMPT,
                history=[{"role": "user", "content": exchange}],
                temperature=0.0,
                max_tokens=300,
            )
            input_tokens, output_tokens = result.input_tokens, result.output_tokens
            record_usage(
                db, user_id, workspace_id, settings.llm_provider, default_model,
                input_tokens, output_tokens,
            )
            facts = json.loads(_strip_code_fence(result.text))
            if isinstance(facts, list):
                for fact in facts[:3]:
                    key = str(fact.get("key", "")).strip()
                    value = str(fact.get("value", "")).strip()
                    if key and value:
                        upsert_memory(
                            workspace_id, user_id, key, value, db, conversation_id=conversation_id
                        )
        except (LLMError, json.JSONDecodeError, AttributeError, TypeError) as exc:
            logger.info("Memory extraction skipped for conversation_id=%s: %s", conversation_id, exc)
            trace_status = TraceStatus.DEGRADED
            trace_error = str(exc)
        except Exception as exc:  # guarantees the "never raises" contract above
            logger.exception("Unexpected memory extraction failure for conversation_id=%s", conversation_id)
            trace_status = TraceStatus.DEGRADED
            trace_error = str(exc)

    input_cost, output_cost, total_cost = estimate_cost_breakdown(default_model, input_tokens, output_tokens)
    record_trace(
        db,
        trace_type=TraceType.MEMORY_EXTRACTION,
        workspace_id=workspace_id,
        user_id=user_id,
        conversation_id=conversation_id,
        provider=settings.llm_provider,
        model=default_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=total_cost,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        latency_ms=span["elapsed_ms"],
        status=trace_status,
        error_message=trace_error,
    )


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _run_extraction_in_background(
    workspace_id: str, user_id: str, conversation_id: str, user_message: str, assistant_message: str
) -> None:
    """Runs in a FastAPI BackgroundTask, after the response has already been
    sent — opens its own short-lived DB session rather than reusing the
    request's (which FastAPI has already torn down by the time background
    tasks execute), matching how any other out-of-request job would need to
    manage its own session lifecycle."""
    from app.database.session import SessionLocal

    db = SessionLocal()
    try:
        extract_and_store_memories(workspace_id, user_id, conversation_id, user_message, assistant_message, db)
    finally:
        db.close()


def schedule_memory_extraction(
    background_tasks,
    workspace_id: str,
    user_id: str,
    conversation_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """Performance optimization (Week 6): moves memory extraction — a full
    second LLM call — off the user-facing request path. `background_tasks` is
    a fastapi.BackgroundTasks instance; Starlette runs it after the response
    is sent, so the chat reply no longer waits on this call's latency."""
    background_tasks.add_task(
        _run_extraction_in_background, workspace_id, user_id, conversation_id, user_message, assistant_message
    )
