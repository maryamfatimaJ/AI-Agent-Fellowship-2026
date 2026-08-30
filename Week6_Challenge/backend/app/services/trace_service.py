import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.tracing_middleware import get_current_trace_id
from app.models.trace import Trace, TraceStatus, TraceType


def record_trace(
    db: Session,
    *,
    trace_type: TraceType,
    workspace_id: str | None = None,
    user_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: float = 0.0,
    status: TraceStatus = TraceStatus.SUCCESS,
    error_message: str | None = None,
    retry_count: int = 0,
    meta: dict | None = None,
) -> Trace:
    trace = Trace(
        trace_id=get_current_trace_id(),
        workspace_id=workspace_id,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        trace_type=trace_type,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        status=status,
        error_message=error_message,
        retry_count=retry_count,
        meta=meta,
    )
    db.add(trace)
    db.commit()
    return trace


@contextmanager
def timed_span():
    """Usage: with timed_span() as span: ...; span['elapsed_ms'] is set on exit."""
    start = time.perf_counter()
    span = {"elapsed_ms": 0.0}
    try:
        yield span
    finally:
        span["elapsed_ms"] = (time.perf_counter() - start) * 1000


@dataclass
class SpanRecorder:
    """Builds the canonical `meta["spans"]` timeline for a trace — the named
    execution stages (request / input_validation / model_call / retrieval /
    agent_decision / tool_call / tool_result / final_response) the trace
    viewer renders as a step-by-step timeline. Not every request has every
    stage; only the stages that actually ran are recorded, in the order they
    ran. Each span carries its own id and absolute start timestamp (in
    addition to duration/status/metadata) so a specific step can be referred
    to individually — e.g. from a future dashboard drill-down — not just
    positionally within the list."""

    spans: list[dict] = field(default_factory=list)

    def add(
        self, name: str, elapsed_ms: float, status: str = "success", error: str | None = None, **metadata
    ) -> dict:
        started_at = datetime.now(timezone.utc)
        span = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "started_at": started_at.isoformat(),
            "duration_ms": round(elapsed_ms, 2),
            "status": status,
            "error": error,
            "metadata": metadata,
        }
        self.spans.append(span)
        return span

    @contextmanager
    def span(self, name: str, **metadata):
        """Usage: with recorder.span("retrieval", query=...) as info: ...
        info["status"] can be set inside the block (defaults to "success");
        info["error"] likewise; any other keys set on `info` are merged into
        the span's metadata."""
        start = time.perf_counter()
        info: dict = {"status": "success", "error": None}
        try:
            yield info
        except Exception as exc:
            info["status"] = "error"
            info["error"] = str(exc)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            status = info.pop("status", "success")
            error = info.pop("error", None)
            self.add(name, elapsed_ms, status=status, error=error, **info)
