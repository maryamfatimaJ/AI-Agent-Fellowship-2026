import re

SECRET_PATTERNS: dict[str, re.Pattern] = {
    "openai_api_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "gemini_api_key": re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "generic_bearer_token": re.compile(r"Bearer [A-Za-z0-9\-_.]{20,}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    "private_key_block": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def scan_for_secrets(text: str) -> list[str]:
    if not text:
        return []
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]


def redact_secrets(text: str) -> str:
    redacted = text
    for name, pattern in SECRET_PATTERNS.items():
        redacted = pattern.sub(f"[REDACTED_{name.upper()}]", redacted)
    return redacted
