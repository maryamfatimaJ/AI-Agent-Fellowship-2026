"""
services/llm_service.py
------------------------
The only file in the whole app that talks to the Gemini API directly.
Every tool or agent node that needs the LLM calls a function here
instead of importing google.genai itself — that keeps the LLM provider
swappable in exactly one place if it's ever changed.
"""

import json
import re
import time

from google import genai
from google.genai import errors as genai_errors

from config import settings

_client = genai.Client(api_key=settings.GEMINI_API_KEY)

# A 429 from the free tier is almost always a per-DAY quota
# (GenerateRequestsPerDayPerProjectPerModel-FreeTier, currently 20/day
# for gemini-2.5-flash) — retrying that immediately can't succeed until
# the quota resets. These retries exist only for the rarer transient
# case where Google's own response includes a short retryDelay, i.e. a
# genuine per-minute throttle rather than the day limit.
_MAX_RATE_LIMIT_RETRIES = 2
# Cap how long a single retry sleeps for, even if Google's retryDelay
# hint asks for more — one /chat request shouldn't hang the browser.
_MAX_RETRY_DELAY_SECONDS = 15


class LLMError(Exception):
    """Raised when the LLM can't be reached or returns something unusable."""
    pass


class LLMQuotaExceededError(LLMError):
    """
    Raised specifically for a 429 RESOURCE_EXHAUSTED response, once
    retries (if any) are exhausted. Kept as its own type — not just a
    generic LLMError — so callers (see execute_tool_with_limits in
    agent/nodes.py) can recognize it and skip further retries instead
    of hammering an already-exhausted quota three times over.
    """
    pass


def _print_full_gemini_error(error, when: str) -> None:
    """
    Print every detail available about a Gemini API error straight to
    the terminal — deliberately NOT simplified or swallowed, so a real
    failure can be diagnosed directly from the server's console output.
    Mirrors the same level of detail gemini_test/test.py prints
    standalone, so the two are directly comparable.
    """
    print("=" * 60)
    print(f"GEMINI API ERROR ({when})")
    print("=" * 60)
    print("Exception type:", type(error).__name__)

    status_code = getattr(error, "code", None)
    if status_code is not None:
        print("Status code:", status_code)

    status_text = getattr(error, "status", None)
    if status_text is not None:
        print("Status:", status_text)

    details = getattr(error, "details", None)
    if details is not None:
        print("Full error details:", details)

    print("Full exception message:", str(error))
    print("=" * 60)


def _extract_retry_delay_seconds(error) -> float | None:
    """Pull Google's suggested retry delay (e.g. "6s") out of the error details, if present."""
    try:
        for detail in error.details.get("error", {}).get("details", []):
            if detail.get("@type", "").endswith("RetryInfo"):
                match = re.match(r"([\d.]+)s", detail.get("retryDelay", ""))
                if match:
                    return float(match.group(1))
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def generate_text(prompt: str) -> str:
    """
    Send a prompt to Gemini and return its plain text reply.

    A 429 gets a small, bounded number of retries ONLY when Google's own
    response includes a short retryDelay (a transient per-minute
    throttle). If there's no such hint, or it's still 429 after
    retrying, this raises LLMQuotaExceededError immediately with a
    clean message instead of continuing to retry a genuinely exhausted
    daily quota.
    """
    last_error = None

    for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
        try:
            response = _client.models.generate_content(
                model=settings.GENERATION_MODEL,
                contents=prompt,
            )
            return response.text
        except genai_errors.ClientError as error:
            _print_full_gemini_error(error, "generate_content — ClientError")
            if error.code != 429:
                raise LLMError("Couldn't get a response from the language model: " + str(error)) from error

            last_error = error
            delay = _extract_retry_delay_seconds(error)
            if delay is None or attempt == _MAX_RATE_LIMIT_RETRIES:
                break  # not transient, or out of retries — report clearly below instead of looping

            time.sleep(min(delay, _MAX_RETRY_DELAY_SECONDS))
        except Exception as error:
            _print_full_gemini_error(error, "generate_content — unexpected exception")
            raise LLMError("Couldn't get a response from the language model: " + str(error)) from error

    _print_full_gemini_error(last_error, "generate_content — giving up after retries")
    raise LLMQuotaExceededError(
        "Trace has hit its Gemini API request limit for now (the free tier allows a limited "
        "number of requests per day, shared across every API key on the same project). "
        "Please try again later once the daily quota resets."
    ) from last_error


def generate_json(prompt: str) -> dict:
    """
    Send a prompt that asks Gemini to reply with ONLY a JSON object, and
    parse that reply into a Python dict.

    Raises LLMError if the model can't be reached, or if what it returns
    isn't valid JSON (Requirement 8: handle an invalid model response
    instead of crashing or silently returning garbage).
    """
    raw_text = generate_text(prompt)

    # Models sometimes wrap JSON in ```json ... ``` fences even when told not to.
    cleaned_text = raw_text.strip()
    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.strip("`")
        if cleaned_text.startswith("json"):
            cleaned_text = cleaned_text[4:]
        cleaned_text = cleaned_text.strip()

    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as error:
        raise LLMError(
            "The language model's response wasn't valid JSON, so it couldn't be used: " + str(error)
        ) from error
