from dataclasses import dataclass, field

from app.guardrails.injection_patterns import scan_for_injection
from app.guardrails.secrets import redact_secrets, scan_for_secrets

_LEAK_WINDOW_WORDS = 8
_LEAK_MIN_PHRASE_LEN = 20


@dataclass
class OutputCheckResult:
    text: str
    triggered_patterns: list[str] = field(default_factory=list)
    system_prompt_leaked: bool = False
    secrets_found: list[str] = field(default_factory=list)
    sanitized: bool = False


def _system_prompt_leaked(output_text: str, system_prompt: str) -> bool:
    """A verbatim multi-word run of the system prompt appearing in the reply is
    a strong signal the model was manipulated into echoing it back — a single
    shared word (e.g. "helpful") is not."""
    words = system_prompt.split()
    output_lower = output_text.lower()
    if len(words) < _LEAK_WINDOW_WORDS:
        phrase = system_prompt.strip().lower()
        return len(phrase) >= _LEAK_MIN_PHRASE_LEN and phrase in output_lower

    for i in range(len(words) - _LEAK_WINDOW_WORDS + 1):
        phrase = " ".join(words[i : i + _LEAK_WINDOW_WORDS]).lower()
        if len(phrase) >= _LEAK_MIN_PHRASE_LEN and phrase in output_lower:
            return True
    return False


def check_output(output_text: str, system_prompt: str) -> OutputCheckResult:
    """Runs after generation: flags system-prompt leakage and echoed injection
    payloads, and redacts any secret-shaped strings before the reply is
    persisted or returned — a real leak (e.g. a key embedded in a RAG document
    that the model echoed back) is sanitized rather than shipped to the user."""
    if not output_text:
        return OutputCheckResult(text=output_text)

    leaked = _system_prompt_leaked(output_text, system_prompt)
    injection_matches = scan_for_injection(output_text)
    secrets_found = scan_for_secrets(output_text)

    text = output_text
    sanitized = False
    if secrets_found:
        text = redact_secrets(text)
        sanitized = True

    triggered = list(injection_matches)
    if leaked:
        triggered.append("system_prompt_leak")

    return OutputCheckResult(
        text=text,
        triggered_patterns=triggered,
        system_prompt_leaked=leaked,
        secrets_found=secrets_found,
        sanitized=sanitized,
    )
