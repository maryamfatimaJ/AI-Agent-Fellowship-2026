"""Provider-agnostic LLM access. Default provider is Gemini (matches the rest of the
repo's weeks); OpenAI is supported as an alternative via LLM_PROVIDER=openai.
"""

import logging
from dataclasses import dataclass, field
from functools import lru_cache

from app.core.config import get_settings
from app.core.events import MODEL_CALLED, log_event
from app.core.retry import call_with_retry, run_with_timeout

logger = logging.getLogger("app.llm")


class LLMError(RuntimeError):
    """Raised when the configured provider fails or has no usable API key."""


class LLMTimeoutError(LLMError):
    """Raised when a provider call exceeds llm_request_timeout_seconds, even
    after retries — kept distinct from LLMError so callers can record a
    'timeout' trace status instead of a generic 'error' one."""


@dataclass
class GenerationResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    retry_count: int = field(default=0)


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict


@dataclass
class AgentGenerationResult:
    text: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    retry_count: int = 0


def _require_key(key: str, provider: str) -> None:
    if not key:
        raise LLMError(f"No API key configured for provider '{provider}'. Set it in backend/.env.")


@lru_cache
def _get_gemini_client():
    """Optimization (Week 6 performance pass): reused across every call instead
    of constructing a new genai.Client() per request. lru_cache with no
    arguments makes this a lazily-initialized module-level singleton — it
    only actually caches once _require_key stops raising (functools.lru_cache
    never caches a call that raised), so a missing key still fails every call
    exactly as before, just without ever caching a client for it."""
    from google import genai

    settings = get_settings()
    _require_key(settings.gemini_api_key, "gemini")
    return genai.Client(api_key=settings.gemini_api_key)


@lru_cache
def _get_openai_client():
    from openai import OpenAI

    settings = get_settings()
    _require_key(settings.openai_api_key, "openai")
    return OpenAI(api_key=settings.openai_api_key, timeout=settings.llm_request_timeout_seconds)


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
    log_event(logger, MODEL_CALLED, provider=provider, model=model or "default", history_length=len(history))

    def _dispatch() -> GenerationResult:
        if provider == "openai":
            return _generate_openai(system_prompt, history, temperature, max_tokens, model)
        return _generate_gemini(system_prompt, history, temperature, max_tokens, model)

    def _dispatch_with_timeout() -> GenerationResult:
        return run_with_timeout(_dispatch, settings.llm_request_timeout_seconds)

    try:
        result, retry_count = call_with_retry(_dispatch_with_timeout)
        result.retry_count = retry_count
        return result
    except TimeoutError as exc:
        logger.warning("LLM generation timed out after retries (provider=%s)", provider)
        raise LLMTimeoutError(f"LLM request timed out: {exc}") from exc
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

    def _dispatch() -> list[list[float]]:
        if provider == "openai":
            return _embed_openai(texts)
        return _embed_gemini(texts, task_type)

    def _dispatch_with_timeout() -> list[list[float]]:
        return run_with_timeout(_dispatch, settings.llm_request_timeout_seconds)

    try:
        result, _retry_count = call_with_retry(_dispatch_with_timeout)
        return result
    except TimeoutError as exc:
        logger.warning("Embedding generation timed out after retries (provider=%s)", provider)
        raise LLMTimeoutError(f"Embedding request timed out: {exc}") from exc
    except LLMError:
        raise
    except Exception as exc:
        logger.exception("Embedding generation failed (provider=%s)", provider)
        raise LLMError(f"Embedding request failed: {exc}") from exc


def generate_with_tools(
    system_prompt: str,
    history: list[dict[str, str]],
    tools: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1024,
    provider: str | None = None,
    model: str | None = None,
) -> AgentGenerationResult:
    """Function-calling variant of generate_reply(), used by the agent
    orchestrator. `tools` is a list of {"name", "description", "parameters"}
    (JSON-schema `parameters`), translated per-provider below. Returns either
    tool_calls to execute, or text if the model chose to answer directly."""
    settings = get_settings()
    provider = provider or settings.llm_provider
    log_event(logger, MODEL_CALLED, provider=provider, model=model or "default", tool_count=len(tools), mode="agent")

    def _dispatch() -> AgentGenerationResult:
        if provider == "openai":
            return _generate_openai_with_tools(system_prompt, history, tools, temperature, max_tokens, model)
        return _generate_gemini_with_tools(system_prompt, history, tools, temperature, max_tokens, model)

    def _dispatch_with_timeout() -> AgentGenerationResult:
        return run_with_timeout(_dispatch, settings.llm_request_timeout_seconds)

    try:
        result, retry_count = call_with_retry(_dispatch_with_timeout)
        result.retry_count = retry_count
        return result
    except TimeoutError as exc:
        logger.warning("LLM tool-call generation timed out after retries (provider=%s)", provider)
        raise LLMTimeoutError(f"LLM tool-call request timed out: {exc}") from exc
    except LLMError:
        raise
    except Exception as exc:
        logger.exception("LLM tool-call generation failed (provider=%s)", provider)
        raise LLMError(f"LLM tool-call request failed: {exc}") from exc


def _generate_gemini_with_tools(
    system_prompt: str,
    history: list[dict[str, str]],
    tools: list[dict],
    temperature: float,
    max_tokens: int,
    model: str | None,
) -> AgentGenerationResult:
    from google.genai import types

    settings = get_settings()
    client = _get_gemini_client()
    contents = [
        types.Content(role=("model" if turn["role"] == "assistant" else "user"), parts=[types.Part(text=turn["content"])])
        for turn in history
    ]
    function_declarations = [
        types.FunctionDeclaration(name=t["name"], description=t["description"], parameters=t["parameters"])
        for t in tools
    ]
    gemini_tools = [types.Tool(function_declarations=function_declarations)] if function_declarations else None

    response = client.models.generate_content(
        model=model or settings.gemini_model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
            tools=gemini_tools,
        ),
    )
    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", 0) or 0
    output_tokens = getattr(usage, "candidates_token_count", 0) or 0

    tool_calls: list[ToolCallRequest] = []
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        parts = getattr(candidates[0].content, "parts", None) or []
        for part in parts:
            function_call = getattr(part, "function_call", None)
            if function_call is not None:
                tool_calls.append(
                    ToolCallRequest(id=function_call.name, name=function_call.name, arguments=dict(function_call.args or {}))
                )

    text = None if tool_calls else (response.text or "")
    return AgentGenerationResult(text=text, tool_calls=tool_calls, input_tokens=input_tokens, output_tokens=output_tokens)


def _generate_openai_with_tools(
    system_prompt: str,
    history: list[dict[str, str]],
    tools: list[dict],
    temperature: float,
    max_tokens: int,
    model: str | None,
) -> AgentGenerationResult:
    import json as _json

    settings = get_settings()
    client = _get_openai_client()
    messages = [{"role": "system", "content": system_prompt}, *history]
    openai_tools = [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
        for t in tools
    ]
    response = client.chat.completions.create(
        model=model or settings.openai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=openai_tools or None,
        tool_choice="auto" if openai_tools else None,
    )
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0

    message = response.choices[0].message
    tool_calls: list[ToolCallRequest] = []
    for call in message.tool_calls or []:
        try:
            arguments = _json.loads(call.function.arguments or "{}")
        except _json.JSONDecodeError:
            arguments = {}
        tool_calls.append(ToolCallRequest(id=call.id, name=call.function.name, arguments=arguments))

    text = None if tool_calls else (message.content or "")
    return AgentGenerationResult(text=text, tool_calls=tool_calls, input_tokens=input_tokens, output_tokens=output_tokens)


def _generate_gemini(
    system_prompt: str,
    history: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    model: str | None,
) -> GenerationResult:
    from google.genai import types

    settings = get_settings()
    client = _get_gemini_client()
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
    from google.genai import types

    settings = get_settings()
    client = _get_gemini_client()
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
    settings = get_settings()
    client = _get_openai_client()
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
    settings = get_settings()
    client = _get_openai_client()
    response = client.embeddings.create(model=settings.openai_embedding_model, input=texts)
    return [item.embedding for item in response.data]
