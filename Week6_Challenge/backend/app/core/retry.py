import concurrent.futures
import logging
from typing import Callable, TypeVar

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.events import RETRY_ATTEMPTED, log_event

logger = logging.getLogger("app.retry")

T = TypeVar("T")

# Duck-typed on error text rather than SDK-specific exception classes, matching
# the existing user_facing_error() pattern in llm_service.py — both Gemini and
# OpenAI SDK errors are classified the same way without importing either SDK
# at module load time.
_RETRYABLE_MARKERS = (
    "resource_exhausted",
    "429",
    "rate limit",
    "timeout",
    "timed out",
    "503",
    "502",
    "500",
    "internal server error",
    "connection reset",
    "connection error",
    "temporarily unavailable",
    "overloaded",
)

_NON_RETRYABLE_MARKERS = (
    "400",
    "401",
    "403",
    "404",
    "not_found",
    "invalid api key",
    "no api key configured",
    "invalid_argument",
    "unsupported file type",
)


def is_retryable(exc: BaseException) -> bool:
    text = str(exc).lower()
    if any(marker in text for marker in _NON_RETRYABLE_MARKERS):
        return False
    return any(marker in text for marker in _RETRYABLE_MARKERS)


def _log_retry_attempt(retry_state) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    wait_seconds = retry_state.next_action.sleep if retry_state.next_action else None
    log_event(
        logger,
        RETRY_ATTEMPTED,
        level=logging.WARNING,
        attempt_number=retry_state.attempt_number,
        wait_seconds=round(wait_seconds, 2) if wait_seconds is not None else None,
        error=str(exc) if exc else None,
    )


def call_with_retry(fn: Callable[[], T]) -> tuple[T, int]:
    """Runs fn() with exponential-backoff retry on transient provider errors
    (rate limits, timeouts, 5xx). Non-retryable errors (bad API key, invalid
    request) fail on the first attempt. Returns (result, retry_count)."""
    settings = get_settings()
    retryer = Retrying(
        stop=stop_after_attempt(settings.llm_max_retries + 1),
        wait=wait_exponential(
            multiplier=settings.llm_retry_backoff_seconds,
            min=settings.llm_retry_backoff_seconds,
            max=10,
        ),
        retry=retry_if_exception(is_retryable),
        reraise=True,
        before_sleep=_log_retry_attempt,
    )
    result = retryer(fn)
    retry_count = retryer.statistics.get("attempt_number", 1) - 1
    return result, retry_count


def run_with_timeout(fn: Callable[[], T], timeout_seconds: float) -> T:
    """Hard backstop timeout enforced from our side, independent of whatever
    timeout (if any) the provider SDK itself honors — the SDK call runs in a
    worker thread so a hang can't block the request indefinitely.

    Deliberately does NOT use `with ThreadPoolExecutor(...) as executor:` —
    the context manager's __exit__ calls shutdown(wait=True), which would
    block until the hung worker thread finishes anyway, defeating the whole
    point of the timeout. shutdown(wait=False) below abandons a still-running
    worker instead (it finishes in the background and is garbage collected;
    Python has no way to forcibly kill a thread)."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError as exc:
        raise TimeoutError(f"Call timed out after {timeout_seconds}s") from exc
    finally:
        executor.shutdown(wait=False)
