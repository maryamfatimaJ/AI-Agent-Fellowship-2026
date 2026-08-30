from dataclasses import dataclass, field

from app.core.config import get_settings
from app.guardrails.injection_patterns import scan_for_injection


@dataclass
class GuardResult:
    allowed: bool
    triggered_patterns: list[str] = field(default_factory=list)
    reason: str | None = None


def check_input(text: str) -> GuardResult:
    """Defense-in-depth on top of the schema-level min_length validation already
    on SendMessageRequest: catches over-length input and flags (or, if
    guardrails_block_on_injection is enabled, blocks) direct prompt-injection
    attempts in the user's own message."""
    settings = get_settings()

    if not text or not text.strip():
        return GuardResult(allowed=False, reason="Message cannot be empty.")

    if len(text) > settings.max_input_chars:
        return GuardResult(
            allowed=False,
            reason=f"Message exceeds the {settings.max_input_chars}-character limit.",
        )

    matches = scan_for_injection(text)
    if matches and settings.guardrails_block_on_injection:
        return GuardResult(
            allowed=False,
            triggered_patterns=matches,
            reason="Message appears to contain an attempt to override system instructions.",
        )
    return GuardResult(allowed=True, triggered_patterns=matches)
