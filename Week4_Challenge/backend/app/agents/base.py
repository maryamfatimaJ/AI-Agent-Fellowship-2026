"""Shared helpers for building the structured execution-log / error records
every agent must emit. Keeping this in one place guarantees every agent logs
invocations the same way."""

from __future__ import annotations

from app.schemas.common import LogLevel
from app.schemas.evidence import EvidenceItem
from app.schemas.execution import ExecutionLogEntry, WorkflowError
from app.utils.errors import EvidentError
from app.utils.ids import new_log_id
from app.utils.time_utils import utc_now_iso


def format_evidence_lines(evidence: list[EvidenceItem]) -> list[str]:
    """Render evidence as compact, LLM-friendly lines shared by every agent
    prompt that needs to present the evidence list (Analyst, Critic, Writer,
    and the bonus specialists)."""

    if not evidence:
        return ["(no evidence available)"]
    return [
        f"{item.evidence_id} · {item.evidence_type.value} · {item.confidence}% · {item.claim}"
        for item in evidence
    ]


def log_entry(
    agent: str,
    message: str,
    *,
    level: LogLevel = LogLevel.INFO,
    tool: str | None = None,
    task_id: str | None = None,
    duration_ms: int | None = None,
    **meta: object,
) -> ExecutionLogEntry:
    return ExecutionLogEntry(
        log_id=new_log_id(),
        timestamp=utc_now_iso(),
        agent=agent,
        level=level,
        message=message,
        tool=tool,
        task_id=task_id,
        duration_ms=duration_ms,
        meta=meta,
    )


def error_entry(agent: str, exc: Exception, *, task_id: str | None = None, recoverable: bool = True) -> WorkflowError:
    if isinstance(exc, EvidentError):
        return WorkflowError(
            error_id=new_log_id(),
            timestamp=utc_now_iso(),
            code=exc.code,
            message=exc.message,
            agent=agent,
            task_id=task_id,
            recoverable=recoverable,
            details=exc.details,
        )
    return WorkflowError(
        error_id=new_log_id(),
        timestamp=utc_now_iso(),
        code="unexpected_error",
        message=str(exc),
        agent=agent,
        task_id=task_id,
        recoverable=recoverable,
        details={},
    )
