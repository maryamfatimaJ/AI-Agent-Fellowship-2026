class GuardrailBlockedError(Exception):
    """Raised when an input guard blocks a request outright (guardrails_block_on_injection=True).
    Caught at the router layer and turned into a 400 response."""

    def __init__(self, message: str, triggered_patterns: list[str]):
        super().__init__(message)
        self.triggered_patterns = triggered_patterns
