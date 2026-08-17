"""Provider-agnostic LLM access. Default provider is Gemini (matches the rest of the
repo's weeks); OpenAI is supported as an alternative via LLM_PROVIDER=openai.
"""

import logging
from dataclasses import dataclass

from app.core.config import get_settings

logger = logging.getLogger("app.llm")


class LLMError(RuntimeError):
    """Raised when the configured provider fails or has no usable API key."""


@dataclass
class GenerationResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


def _require_key(key: str, provider: str) -> None:
    if not key:
        raise LLMError(f"No API key configured for provider '{provider}'. Set it in backend/.env.")


def user_facing_error(exc: Exception) -> str:
    """Never surface raw provider error text (quota internals, URLs, model
    identifiers) to the end user — full detail is logged server-side by the caller."""
    text = str(exc)
    if "RESOURCE_EXHAUSTED" in text or "429" in text or "rate limit" in text.lower():
        return "The assistant is temporarily rate-limited by the model provider. Please wait a moment and try again."
    return "I couldn't reach the language model just now. Please try again in a moment."


def generate_reply(
    system_prompt: str,
    history: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 1024,
    provider: str | None = None,
    model: str | None = None,
) -> GenerationResult:
    """history is a list of {"role": "user"|"assistant", "content": str}, oldest first."""
    settings = get_settings()
    provider = provider or settings.llm_provider

    try:
        if provider == "openai":
            return _generate_openai(system_prompt, history, temperature, max_tokens, model)
        return _generate_gemini(system_prompt, history, temperature, max_tokens, model)
    except LLMError:
        raise
    except Exception as exc:  # provider SDK errors are not worth typing individually here
        logger.exception("LLM generation failed (provider=%s)", provider)
        raise LLMError(f"LLM request failed: {exc}") from exc


def embed_texts(
    texts: list[str], provider: str | None = None, task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    settings = get_settings()
    provider = provider or settings.llm_provider

    try:
        if provider == "openai":
            return _embed_openai(texts)
        return _embed_gemini(texts, task_type)
    except LLMError:
        raise
    except Exception as exc:
        logger.exception("Embedding generation failed (provider=%s)", provider)
        raise LLMError(f"Embedding request failed: {exc}") from exc


def _generate_gemini(
    system_prompt: str,
    history: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    model: str | None,
) -> GenerationResult:
    from google import genai
    from google.genai import types

    settings = get_settings()
    _require_key(settings.gemini_api_key, "gemini")

    client = genai.Client(api_key=settings.gemini_api_key)
    contents = [
        types.Content(role=("model" if turn["role"] == "assistant" else "user"), parts=[types.Part(text=turn["content"])])
        for turn in history
    ]
    response = client.models.generate_content(
        model=model or settings.gemini_model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0
    return GenerationResult(text=response.text or "", input_tokens=input_tokens, output_tokens=output_tokens)


def _embed_gemini(texts: list[str], task_type: str) -> list[list[float]]:
    from google import genai
    from google.genai import types

    settings = get_settings()
    _require_key(settings.gemini_api_key, "gemini")

    client = genai.Client(api_key=settings.gemini_api_key)
    result = client.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return [embedding.values for embedding in result.embeddings]


def _generate_openai(
    system_prompt: str,
    history: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    model: str | None,
) -> GenerationResult:
    from openai import OpenAI

    settings = get_settings()
    _require_key(settings.openai_api_key, "openai")

    client = OpenAI(api_key=settings.openai_api_key)
    messages = [{"role": "system", "content": system_prompt}, *history]
    response = client.chat.completions.create(
        model=model or settings.openai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0
    return GenerationResult(
        text=response.choices[0].message.content or "", input_tokens=input_tokens, output_tokens=output_tokens
    )


def _embed_openai(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    settings = get_settings()
    _require_key(settings.openai_api_key, "openai")

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(model=settings.openai_embedding_model, input=texts)
    return [item.embedding for item in response.data]
