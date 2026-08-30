"""Performance optimization #2 (Week 6): the Gemini/OpenAI SDK clients are
constructed once and reused, instead of once per LLM call. These tests fake
out the SDK constructors to count how many times they're actually invoked.
"""

from app.services.llm_service import _get_gemini_client, _get_openai_client


def test_gemini_client_is_constructed_once_and_reused(monkeypatch):
    _get_gemini_client.cache_clear()
    construction_count = {"n": 0}

    class _FakeClient:
        def __init__(self, api_key):
            construction_count["n"] += 1

    monkeypatch.setattr("google.genai.Client", _FakeClient)
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "gemini_api_key", "fake-key-for-test")

    client_a = _get_gemini_client()
    client_b = _get_gemini_client()
    client_c = _get_gemini_client()

    assert client_a is client_b is client_c
    assert construction_count["n"] == 1
    _get_gemini_client.cache_clear()


def test_openai_client_is_constructed_once_and_reused(monkeypatch):
    _get_openai_client.cache_clear()
    construction_count = {"n": 0}

    class _FakeClient:
        def __init__(self, api_key, timeout):
            construction_count["n"] += 1

    monkeypatch.setattr("openai.OpenAI", _FakeClient)
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "openai_api_key", "fake-key-for-test")

    client_a = _get_openai_client()
    client_b = _get_openai_client()

    assert client_a is client_b
    assert construction_count["n"] == 1
    _get_openai_client.cache_clear()


def test_missing_api_key_never_gets_cached_and_keeps_failing(monkeypatch):
    """functools.lru_cache doesn't cache calls that raise — confirms a missing
    key fails every single call rather than caching a broken/absent client."""
    from app.services.llm_service import LLMError

    _get_gemini_client.cache_clear()
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "gemini_api_key", "")

    for _ in range(3):
        try:
            _get_gemini_client()
            assert False, "expected LLMError"
        except LLMError:
            pass
    _get_gemini_client.cache_clear()
