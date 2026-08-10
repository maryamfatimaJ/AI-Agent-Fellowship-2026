"""Provider-agnostic LLM service.

Every agent goes through this module rather than calling an SDK directly, so
that:

- the provider (OpenAI / Gemini) is a single config switch,
- every structured-output call is validated against a Pydantic schema with a
  bounded repair-retry loop (handles "Invalid JSON" / "Invalid Structured
  Output" failure modes), and
- every call is timed and logged uniformly for the execution trace.
"""

from __future__ import annotations

import asyncio
import time
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from app.config.logging_config import get_logger
from app.config.settings import Settings, get_settings
from app.utils.errors import InvalidStructuredOutputError, LLMAPIError, LLMTimeoutError
from app.utils.json_utils import extract_json_object

logger = get_logger("services.llm")

_ModelT = TypeVar("_ModelT", bound=BaseModel)

_SCHEMA_INSTRUCTIONS_TEMPLATE = """
You must respond with a single JSON object and nothing else — no markdown
fences, no commentary before or after it. The object MUST conform exactly to
this JSON Schema:

{schema}

Return ONLY the JSON object.
""".strip()


class LLMCallResult(BaseModel):
    """Metadata about a completed structured LLM call, for the execution log."""

    provider: str
    model: str
    attempts: int
    duration_ms: int


class LLMService:
    """Thin, provider-agnostic wrapper around OpenAI and Gemini chat APIs."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._openai_client = None
        self._gemini_configured = False

    # -- public API --------------------------------------------------------

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[_ModelT],
    ) -> tuple[_ModelT, LLMCallResult]:
        """Call the configured LLM and parse+validate its output as `response_model`.

        Retries up to `settings.llm_max_retries` times. On JSON/validation
        failures, the retry prompt includes the specific error so the model
        can self-correct. On transport failures, retries with backoff.
        """

        schema_instructions = _SCHEMA_INSTRUCTIONS_TEMPLATE.format(
            schema=response_model.model_json_schema()
        )
        full_system_prompt = f"{system_prompt}\n\n{schema_instructions}"

        max_attempts = max(1, self.settings.llm_max_retries)
        current_user_prompt = user_prompt
        last_error: Exception | None = None
        start = time.perf_counter()

        for attempt in range(1, max_attempts + 1):
            try:
                raw_text = await self._call_provider(full_system_prompt, current_user_prompt)
            except (LLMTimeoutError, LLMAPIError) as exc:
                last_error = exc
                logger.warning("llm.transport_error", attempt=attempt, error=str(exc))
                if attempt >= max_attempts:
                    raise
                await asyncio.sleep(min(2 ** attempt, 8))
                continue

            try:
                data = extract_json_object(raw_text)
                parsed = response_model.model_validate(data)
            except Exception as exc:  # noqa: BLE001 - repair loop catches invalid JSON and schema mismatches alike
                last_error = exc
                logger.warning(
                    "llm.structured_output_invalid",
                    attempt=attempt,
                    error=str(exc),
                    raw_preview=raw_text[:300],
                )
                if attempt >= max_attempts:
                    break
                current_user_prompt = (
                    f"{user_prompt}\n\n"
                    f"Your previous response was invalid: {exc}\n"
                    "Return ONLY a corrected JSON object matching the schema exactly."
                )
                continue

            duration_ms = int((time.perf_counter() - start) * 1000)
            meta = LLMCallResult(
                provider=self.settings.llm_provider,
                model=self._model_name(),
                attempts=attempt,
                duration_ms=duration_ms,
            )
            return parsed, meta

        raise InvalidStructuredOutputError(
            f"LLM failed to produce valid structured output after {max_attempts} attempts",
            details={"last_error": str(last_error)},
        )

    # -- provider dispatch ---------------------------------------------------

    async def _call_provider(self, system_prompt: str, user_prompt: str) -> str:
        if self.settings.llm_provider == "openai":
            return await self._call_openai(system_prompt, user_prompt)
        if self.settings.llm_provider == "gemini":
            return await self._call_gemini(system_prompt, user_prompt)
        raise LLMAPIError(f"Unsupported LLM provider: {self.settings.llm_provider}")

    async def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        try:
            from openai import APIError, APITimeoutError, AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - dependency always installed in prod
            raise LLMAPIError("openai package is not installed") from exc

        if not self.settings.openai_api_key:
            raise LLMAPIError("OPENAI_API_KEY is not configured")

        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                timeout=self.settings.llm_request_timeout_seconds,
            )

        try:
            response = await self._openai_client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_output_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except APITimeoutError as exc:
            raise LLMTimeoutError("OpenAI request timed out") from exc
        except APIError as exc:
            raise LLMAPIError(f"OpenAI API error: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMAPIError("OpenAI returned an empty completion")
        return content

    async def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        try:
            import google.generativeai as genai
            from google.api_core.exceptions import DeadlineExceeded, GoogleAPIError
        except ImportError as exc:  # pragma: no cover
            raise LLMAPIError("google-generativeai package is not installed") from exc

        if not self.settings.gemini_api_key:
            raise LLMAPIError("GEMINI_API_KEY is not configured")

        if not self._gemini_configured:
            genai.configure(api_key=self.settings.gemini_api_key)
            self._gemini_configured = True

        model = genai.GenerativeModel(
            model_name=self.settings.gemini_model,
            system_instruction=system_prompt,
        )

        try:
            response = await asyncio.wait_for(
                model.generate_content_async(
                    user_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=self.settings.llm_temperature,
                        max_output_tokens=self.settings.llm_max_output_tokens,
                        response_mime_type="application/json",
                    ),
                ),
                timeout=self.settings.llm_request_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise LLMTimeoutError("Gemini request timed out") from exc
        except DeadlineExceeded as exc:
            raise LLMTimeoutError("Gemini request exceeded deadline") from exc
        except GoogleAPIError as exc:
            raise LLMAPIError(f"Gemini API error: {exc}") from exc

        if not response.text:
            raise LLMAPIError("Gemini returned an empty completion")
        return response.text

    def _model_name(self) -> str:
        if self.settings.llm_provider == "openai":
            return self.settings.openai_model
        return self.settings.gemini_model


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    return LLMService()
