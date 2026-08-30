import json
import logging
import sys
from pathlib import Path

from app.core.config import get_settings


class TraceIdFilter(logging.Filter):
    """Attaches the current request's trace id to every log record so log lines
    can be correlated with the traces table and the trace viewer."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from app.core.tracing_middleware import get_current_trace_id

            record.trace_id = get_current_trace_id()
        except Exception:
            record.trace_id = "-"
        return True


_STANDARD_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
    "trace_id",
}


class JSONFormatter(logging.Formatter):
    """Every non-standard attribute passed via `extra={...}` (see
    app/core/events.py::log_event) is folded into the JSON line as its own
    field — this is what makes a structured event (event name + context)
    queryable from the log file rather than needing to regex a message
    string. Never pass secrets/passwords/chain-of-thought as an extra field."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_ATTRS or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except TypeError:
                payload[key] = str(value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    text_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | [%(trace_id)s] | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    trace_filter = TraceIdFilter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(text_formatter)
    console_handler.addFilter(trace_filter)

    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(text_formatter)
    file_handler.addFilter(trace_filter)

    # Machine-readable structured log, one JSON object per line, for the trace
    # viewer / log search to parse without regexing the human-readable file.
    json_handler = logging.FileHandler(log_dir / "app.jsonl", encoding="utf-8")
    json_handler.setFormatter(JSONFormatter())
    json_handler.addFilter(trace_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(json_handler)
