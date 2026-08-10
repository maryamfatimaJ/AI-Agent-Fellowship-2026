import json
import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.memory import Memory, MemoryType
from app.services.llm_service import LLMError, generate_reply
from app.services.usage_service import record_usage

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
    """Best-effort background-ish extraction. Never raises — a failure here must not
    break the chat turn that triggered it."""
    try:
        settings = get_settings()
        exchange = f"User: {user_message}\nAssistant: {assistant_message}"
        result = generate_reply(
            system_prompt=_EXTRACTION_SYSTEM_PROMPT,
            history=[{"role": "user", "content": exchange}],
            temperature=0.0,
            max_tokens=300,
        )
        record_usage(
            db, user_id, workspace_id, settings.llm_provider, settings.gemini_model,
            result.input_tokens, result.output_tokens,
        )
        facts = json.loads(_strip_code_fence(result.text))
        if not isinstance(facts, list):
            return

        for fact in facts[:3]:
            key = str(fact.get("key", "")).strip()
            value = str(fact.get("value", "")).strip()
            if key and value:
                upsert_memory(
                    workspace_id, user_id, key, value, db, conversation_id=conversation_id
                )
    except (LLMError, json.JSONDecodeError, AttributeError, TypeError):
        logger.info("Memory extraction skipped for conversation_id=%s", conversation_id)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text.strip()
