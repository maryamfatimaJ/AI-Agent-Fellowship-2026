import time

import pytest

from app.core.retry import run_with_timeout
from app.services.llm_service import LLMTimeoutError, generate_reply


def test_run_with_timeout_returns_result_when_fast_enough():
    assert run_with_timeout(lambda: "done", timeout_seconds=1.0) == "done"


def test_run_with_timeout_raises_timeout_error_when_too_slow():
    def slow():
        time.sleep(0.5)
        return "too late"

    with pytest.raises(TimeoutError):
        run_with_timeout(slow, timeout_seconds=0.05)


def test_generate_reply_surfaces_persistent_timeout_as_llm_timeout_error(monkeypatch):
    """Failure injection: simulate the provider SDK call hanging past the
    configured timeout on every retry attempt, and confirm generate_reply()
    maps that to LLMTimeoutError rather than letting it propagate raw or
    hang the caller."""

    def hangs_forever(*args, **kwargs):
        time.sleep(1.0)
        raise AssertionError("should have been interrupted by the timeout")

    monkeypatch.setattr("app.services.llm_service._generate_gemini", hangs_forever)
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "0.1")
    monkeypatch.setenv("LLM_MAX_RETRIES", "0")

    with pytest.raises(LLMTimeoutError):
        generate_reply(system_prompt="hi", history=[], provider="gemini")

    get_settings.cache_clear()
