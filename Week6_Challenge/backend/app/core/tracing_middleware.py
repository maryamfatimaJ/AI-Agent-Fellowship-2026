import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.events import REQUEST_COMPLETED, REQUEST_RECEIVED, log_event

logger = logging.getLogger("app.request")

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def get_current_trace_id() -> str:
    """Returns the trace id for the in-flight request, generating one if called
    outside a traced request (e.g. from a script or test with no middleware)."""
    trace_id = _trace_id_var.get()
    if trace_id is None:
        trace_id = str(uuid.uuid4())
        _trace_id_var.set(trace_id)
    return trace_id


def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)


class TracingMiddleware(BaseHTTPMiddleware):
    """Assigns a trace id to every request so downstream LLM/RAG/memory calls can
    be correlated back to the request that triggered them, and reports overall
    request latency via a response header. Logs request_received/
    request_completed — method and path only, never the request body (which
    may contain user message content) or any header value."""

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = str(uuid.uuid4())
        token = _trace_id_var.set(trace_id)
        start = time.perf_counter()
        log_event(logger, REQUEST_RECEIVED, method=request.method, path=request.url.path)
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            log_event(
                logger,
                REQUEST_COMPLETED,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(elapsed_ms, 2),
            )
        finally:
            _trace_id_var.reset(token)
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response
