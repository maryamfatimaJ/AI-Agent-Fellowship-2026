"""Named structured-logging events, used throughout the request/agent/RAG
pipeline instead of ad-hoc log messages. Each call becomes one JSON line
(app/logs/app.jsonl, see logging_config.JSONFormatter) carrying the event
name, the current trace id (attached automatically by TraceIdFilter), and
whatever contextual fields the call site passes — enough to reconstruct what
happened for a given request without re-running it.

Event vocabulary (deliberately fixed, not free-form strings, so a log search
can rely on it): request_received, model_called, retrieval_started,
retrieval_completed, tool_selected, tool_succeeded, tool_failed,
retry_attempted, guardrail_triggered, evaluation_started, evaluation_completed,
request_completed. evaluation_started/evaluation_completed each fire twice at
two granularities, distinguished by a `scope` field: once per whole run
(scope="run", carrying run_id/n_cases/summary) and once per case
(scope="case", carrying test_id/category/passed) — see evaluation/runner.py.

Never pass secrets, passwords, or full chain-of-thought as a field — only
short, already-sanitized previews (see chat_service._preview()).
"""

import logging

REQUEST_RECEIVED = "request_received"
REQUEST_COMPLETED = "request_completed"
MODEL_CALLED = "model_called"
RETRIEVAL_STARTED = "retrieval_started"
RETRIEVAL_COMPLETED = "retrieval_completed"
TOOL_SELECTED = "tool_selected"
TOOL_SUCCEEDED = "tool_succeeded"
TOOL_FAILED = "tool_failed"
RETRY_ATTEMPTED = "retry_attempted"
GUARDRAIL_TRIGGERED = "guardrail_triggered"
EVALUATION_STARTED = "evaluation_started"
EVALUATION_COMPLETED = "evaluation_completed"


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields) -> None:
    """Emits one structured log record for `event`, carrying `fields` as
    extra JSON attributes (see logging_config.JSONFormatter, which folds any
    non-standard LogRecord attribute into the JSON line automatically)."""
    logger.log(level, event, extra={"event": event, **fields})
