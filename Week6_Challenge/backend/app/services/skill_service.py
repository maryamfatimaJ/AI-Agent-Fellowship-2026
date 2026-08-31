import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message, MessageRole
from app.models.skill import Skill
from app.models.trace import TraceStatus, TraceType
from app.services.llm_service import LLMError, LLMTimeoutError, default_model_for_provider, generate_reply, user_facing_error
from app.services.trace_service import record_trace, timed_span
from app.services.usage_service import estimate_cost_breakdown, record_usage

logger = logging.getLogger("app.skills")


def run_skill(
    skill: Skill,
    input_text: str,
    user_id: str,
    db: Session,
    assistant: Assistant | None = None,
    conversation: Conversation | None = None,
) -> tuple[str, Message | None, Message | None]:
    """Generic skill execution: build a system prompt from the skill's config, call the
    LLM, and — if a conversation is provided — persist the exchange as real messages so
    the skill's output becomes part of that conversation's normal history (not a
    side-channel result). Returns (output_text, user_message_or_None, assistant_message_or_None).
    """
    settings = get_settings()
    config = skill.config or {}
    skill_prompt = config.get("prompt_template", "Perform the requested task on the input below.")

    system_prompt = skill_prompt
    if assistant and assistant.personality:
        system_prompt += f"\n\nMatch this tone: {assistant.personality}."

    provider = assistant.model_provider if assistant else settings.llm_provider
    model = assistant.model_name if assistant else None
    temperature = assistant.temperature if assistant else 0.5
    max_tokens = assistant.max_tokens if assistant else 1024

    user_message = None
    assistant_message = None
    labeled_input = f"[Skill: {skill.name}]\n{input_text}"

    if conversation is not None:
        user_message = Message(conversation_id=conversation.id, role=MessageRole.USER, content=labeled_input)
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
        if conversation.title is None:
            conversation.title = f"{skill.name}: {input_text[:40]}"
            db.commit()

    model_name = model or default_model_for_provider(provider)
    input_tokens = output_tokens = retry_count = 0
    trace_status = TraceStatus.SUCCESS
    trace_error: str | None = None

    with timed_span() as skill_span:
        try:
            result = generate_reply(
                system_prompt=system_prompt,
                history=[{"role": "user", "content": input_text}],
                temperature=temperature,
                max_tokens=max_tokens,
                provider=provider,
                model=model,
            )
            output = result.text
            input_tokens, output_tokens = result.input_tokens, result.output_tokens
            retry_count = result.retry_count
            if retry_count:
                trace_status = TraceStatus.RETRIED
            record_usage(db, user_id, skill.workspace_id, provider, model_name, input_tokens, output_tokens)
        except LLMTimeoutError as exc:
            logger.warning("Skill execution timed out: %s", exc)
            output = user_facing_error(exc)
            trace_status = TraceStatus.TIMEOUT
            trace_error = str(exc)
        except LLMError as exc:
            logger.warning("Skill execution failed: %s", exc)
            output = user_facing_error(exc)
            trace_status = TraceStatus.ERROR
            trace_error = str(exc)

    input_cost, output_cost, total_cost = estimate_cost_breakdown(model_name, input_tokens, output_tokens)
    record_trace(
        db,
        trace_type=TraceType.SKILL,
        workspace_id=skill.workspace_id,
        user_id=user_id,
        conversation_id=conversation.id if conversation else None,
        provider=provider,
        model=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=total_cost,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        latency_ms=skill_span["elapsed_ms"],
        status=trace_status,
        error_message=trace_error,
        retry_count=retry_count,
        meta={"skill_name": skill.name},
    )

    if conversation is not None:
        assistant_message = Message(conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=output)
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)

    return output, user_message, assistant_message
