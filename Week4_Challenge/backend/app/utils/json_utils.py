"""Defensive JSON extraction for LLM outputs.

LLMs frequently wrap JSON in markdown fences, prepend commentary, or emit
trailing commas. This module isolates the "repair" logic so the LLM service
can retry with a clear, structured error instead of crashing the workflow.
"""

from __future__ import annotations

import json
import re

from app.utils.errors import InvalidJSONError

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json_object(raw_text: str) -> dict:
    """Best-effort extraction of a single JSON object from raw LLM text.

    Raises:
        InvalidJSONError: if no valid JSON object could be recovered.
    """

    if not raw_text or not raw_text.strip():
        raise InvalidJSONError("LLM returned an empty response", details={"raw": raw_text})

    candidates: list[str] = []

    fence_match = _FENCE_RE.search(raw_text)
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    candidates.append(raw_text.strip())

    stripped = raw_text.strip()
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(stripped[first_brace : last_brace + 1])

    last_error: Exception | None = None
    for candidate in candidates:
        cleaned = _strip_trailing_commas(candidate)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:  # try the next candidate
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed
        last_error = InvalidJSONError("Parsed JSON was not an object")

    raise InvalidJSONError(
        "Could not extract a valid JSON object from LLM output",
        details={"raw": raw_text[:2000], "error": str(last_error) if last_error else None},
    )


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)
