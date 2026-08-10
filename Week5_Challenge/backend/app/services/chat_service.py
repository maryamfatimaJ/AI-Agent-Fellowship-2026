import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.memory.memory_service import extract_and_store_memories, format_memories_for_prompt, get_context_memories
from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message, MessageRole
from app.rag.retrieval import retrieve_relevant_chunks
from app.services.llm_service import LLMError, generate_reply
from app.services.usage_service import record_usage

logger = logging.getLogger("app.chat")

_DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


def _build_system_prompt(assistant: Assistant, memories, rag_context: list[dict]) -> str:
    parts = [assistant.system_prompt or _DEFAULT_SYSTEM_PROMPT]

    if assistant.role:
        parts.append(f"Your role: {assistant.role}.")
    if assistant.personality:
        parts.append(f"Personality: {assistant.personality}.")
    if assistant.response_style:
        parts.append(f"Response style: {assistant.response_style}.")

    memory_block = format_memories_for_prompt(memories)
    if memory_block:
        parts.append(memory_block)

    if rag_context:
        context_lines = "\n\n".join(
            f"[Source: {item['filename']}, chunk {item['chunk_index']}]\n{item['snippet']}"
            for item in rag_context
        )
        parts.append(
            "Relevant excerpts from the workspace's uploaded documents:\n"
            f"{context_lines}\n\n"
            "When you use these excerpts in your answer, mention which source they came from."
        )

    return "\n\n".join(parts)


def send_message(
    conversation: Conversation, assistant: Assistant, user_content: str, user_id: str, db: Session
) -> tuple[Message, Message]:
    settings = get_settings()

    user_message = Message(conversation_id=conversation.id, role=MessageRole.USER, content=user_content)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    if conversation.title is None:
        conversation.title = user_content[:60]
        db.commit()

    memories = get_context_memories(conversation.workspace_id, user_id, db)
    rag_context = retrieve_relevant_chunks(conversation.workspace_id, user_content, db)
    system_prompt = _build_system_prompt(assistant, memories, rag_context)

    history_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(settings.conversation_history_limit)
        .all()
    )
    history_messages.reverse()
    history = [
        {"role": "user" if m.role == MessageRole.USER else "assistant", "content": m.content}
        for m in history_messages
        if m.role in (MessageRole.USER, MessageRole.ASSISTANT)
    ]

    try:
        result = generate_reply(
            system_prompt=system_prompt,
            history=history,
            temperature=assistant.temperature,
            max_tokens=assistant.max_tokens,
            provider=assistant.model_provider,
            model=assistant.model_name,
        )
        reply_text = result.text
        default_model = settings.openai_model if assistant.model_provider == "openai" else settings.gemini_model
        record_usage(
            db,
            user_id,
            conversation.workspace_id,
            assistant.model_provider,
            assistant.model_name or default_model,
            result.input_tokens,
            result.output_tokens,
        )
    except LLMError as exc:
        logger.warning("LLM generation failed: %s", exc)
        reply_text = (
            "I couldn't reach the language model just now "
            f"({exc}). Please check the API key configuration and try again."
        )

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=reply_text,
        citations=rag_context or None,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    extract_and_store_memories(
        conversation.workspace_id, user_id, conversation.id, user_content, reply_text, db
    )

    return user_message, assistant_message
