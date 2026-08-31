import pytest

from app.core.retry import call_with_retry, is_retryable


@pytest.mark.parametrize(
    "message,expected",
    [
        ("429 RESOURCE_EXHAUSTED: quota exceeded", True),
        ("Rate limit reached, please slow down", True),
        ("Request timed out after 30s", True),
        ("503 Service Unavailable", True),
        ("connection reset by peer", True),
        ("401 Unauthorized: invalid api key", False),
        ("400 Bad Request: invalid_argument", False),
        ("Unsupported file type: .exe", False),
        # A wrong/deprecated model name (404) can never be fixed by retrying — found via a
        # live gemini-2.5-flash retirement this phase; retrying a 404 just wastes time and
        # delays the user-facing error for no benefit.
        ("404 NOT_FOUND: this model is no longer available to new users", False),
    ],
)
def test_is_retryable_classifies_transient_vs_permanent_errors(message, expected):
    assert is_retryable(RuntimeError(message)) is expected


def test_call_with_retry_succeeds_first_try_reports_zero_retries():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    result, retry_count = call_with_retry(fn)
    assert result == "ok"
    assert retry_count == 0
    assert len(calls) == 1


def test_call_with_retry_retries_transient_failures_then_succeeds():
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("503 Service Unavailable")
        return "recovered"

    result, retry_count = call_with_retry(flaky)
    assert result == "recovered"
    assert retry_count == 2
    assert attempts["count"] == 3


def test_call_with_retry_does_not_retry_permanent_failures():
    attempts = {"count": 0}

    def always_fails():
        attempts["count"] += 1
        raise RuntimeError("401 Unauthorized: invalid api key")

    with pytest.raises(RuntimeError, match="invalid api key"):
        call_with_retry(always_fails)

    assert attempts["count"] == 1


def test_call_with_retry_exhausts_after_max_retries_and_reraises():
    attempts = {"count": 0}

    def always_transient_failure():
        attempts["count"] += 1
        raise RuntimeError("timeout")

    with pytest.raises(RuntimeError, match="timeout"):
        call_with_retry(always_transient_failure)

    # settings.llm_max_retries defaults to 2 => 1 initial attempt + 2 retries = 3 total
    assert attempts["count"] == 3
