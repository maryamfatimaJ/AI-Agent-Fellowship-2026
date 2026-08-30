"""LLM-as-a-judge: scores a single reply on a 1-5 rubric across correctness,
relevance, completeness, clarity, and groundedness — the subjective/semantic
criteria that deterministic code cannot reliably check (see
deterministic_evaluators.py for the objective checks: tool selection, tool
arguments, structured output, citations, approval compliance, forbidden
actions). Uses the same generate_reply() as the rest of the app (mocked in
tests exactly like every other LLM call), at temperature 0 for repeatability.

The judge's output is validated against a Pydantic schema (JudgeScore) before
being trusted — a response that doesn't parse as JSON, or parses but fails
schema validation (score out of range, wrong type, missing field), is treated
identically to a judge failure: null score, in the never-raises fallback
below, never a fabricated result.
"""

import json
import logging

from pydantic import BaseModel, Field, ValidationError

from app.services.llm_service import LLMError, generate_reply

logger = logging.getLogger("app.evaluation.judge")

# Bumped whenever _JUDGE_SYSTEM_PROMPT's wording changes meaningfully — stored
# on every EvaluationResult (judge_prompt_version) alongside judge_score, so a
# future prompt-versioning/regression-testing pass can tell "scores changed
# because the assistant's prompt changed" apart from "scores changed because
# the JUDGE's prompt changed" (prompt_sensitivity, see JUDGE_LIMITATIONS in
# human_comparison.py — the judge's own prompt is not immune to that).
JUDGE_PROMPT_VERSION = "v1"

# Deliberately asks for a short `explanation`, not a full reasoning trace —
# the judge's internal deliberation (if any) is never surfaced or stored.
_JUDGE_SYSTEM_PROMPT = (
    "You are an impartial evaluator scoring an AI assistant's reply to a user request. "
    "Score the reply from 1 (very poor) to 5 (excellent) on each of these five dimensions:\n"
    "- correctness: is the reply factually and logically right?\n"
    "- relevance: does it actually address what the user asked?\n"
    "- completeness: does it cover everything the request needed, without leaving out key parts?\n"
    "- clarity: is it well-organized and easy to understand?\n"
    "- groundedness: if reference context was provided, does the reply stick to it rather than "
    "invent facts not supported by that context or general knowledge?\n\n"
    "If reference context was NOT provided, score groundedness based on whether the reply avoids "
    "inventing specific facts it couldn't know.\n\n"
    "Reply with ONLY a JSON object shaped exactly like this — no other text, and do not include "
    "your step-by-step reasoning, only a brief final explanation:\n"
    '{"correctness": 1-5, "relevance": 1-5, "completeness": 1-5, "clarity": 1-5, '
    '"groundedness": 1-5, "explanation": "one or two sentences on why these scores"}'
)

_SCORE_DIMENSIONS = ("correctness", "relevance", "completeness", "clarity", "groundedness")


class JudgeScore(BaseModel):
    """Schema the judge's raw JSON output is validated against. A response
    that fails this validation (out-of-range score, wrong type, missing
    field) is treated as a judge failure, not silently coerced."""

    correctness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    groundedness: int = Field(ge=1, le=5)
    explanation: str = Field(max_length=1000)

    @property
    def overall_score(self) -> float:
        return round(
            (self.correctness + self.relevance + self.completeness + self.clarity + self.groundedness) / 5, 2
        )


def _build_judge_prompt(
    user_input: str, reply: str, reference_context: str | None, expected_behavior: str | None
) -> str:
    parts = [f"User request:\n{user_input}", f"\nAssistant reply:\n{reply}"]
    if expected_behavior:
        parts.append(f"\nExpected behavior for this request: {expected_behavior}")
    if reference_context:
        parts.append(f"\nReference context the assistant had access to (for groundedness):\n{reference_context}")
    return "\n".join(parts)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text.strip()


def judge_reply(
    user_input: str,
    reply: str,
    reference_context: str | None = None,
    expected_behavior: str | None = None,
) -> dict:
    """Returns a dict with the 5 dimension scores, overall_score, explanation,
    and error (None on success). Never raises — every failure mode (LLM
    error, unparseable JSON, schema-invalid JSON) degrades to a null-score
    dict with `error` set, so a judge outage never aborts an evaluation run."""
    try:
        result = generate_reply(
            system_prompt=_JUDGE_SYSTEM_PROMPT,
            history=[
                {
                    "role": "user",
                    "content": _build_judge_prompt(user_input, reply, reference_context, expected_behavior),
                }
            ],
            temperature=0.0,
            max_tokens=300,
        )
        raw = json.loads(_strip_code_fence(result.text))
        score = JudgeScore.model_validate(raw)
        return {
            "correctness": score.correctness,
            "relevance": score.relevance,
            "completeness": score.completeness,
            "clarity": score.clarity,
            "groundedness": score.groundedness,
            "overall_score": score.overall_score,
            "explanation": score.explanation,
            "error": None,
            "judge_prompt_version": JUDGE_PROMPT_VERSION,
        }
    except (LLMError, json.JSONDecodeError, ValidationError, AttributeError, TypeError) as exc:
        logger.warning("LLM judge failed or returned schema-invalid output, falling back to a null score: %s", exc)
        return {
            **{dim: None for dim in _SCORE_DIMENSIONS},
            "overall_score": None,
            "explanation": "judge unavailable",
            "error": str(exc),
            "judge_prompt_version": JUDGE_PROMPT_VERSION,
        }
