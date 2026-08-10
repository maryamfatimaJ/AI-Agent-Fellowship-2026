"""Execution trace schemas. These record WHAT happened (agent, tool, timing,
handoff, error) — never the model's chain-of-thought."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import LogLevel


class ExecutionLogEntry(BaseModel):
    log_id: str
    timestamp: str
    agent: str
    level: LogLevel = LogLevel.INFO
    message: str
    tool: str | None = None
    task_id: str | None = None
    duration_ms: int | None = None
    meta: dict = Field(default_factory=dict)


class WorkflowError(BaseModel):
    error_id: str
    timestamp: str
    code: str
    message: str
    agent: str | None = None
    task_id: str | None = None
    recoverable: bool = True
    details: dict = Field(default_factory=dict)


class ExecutionTrace(BaseModel):
    """The compiled, top-level summary produced by the final `execution_log`
    graph stage — everything a grader or auditor needs, in one object."""

    run_id: str
    user_request: str
    agents_invoked: list[str] = Field(default_factory=list)
    tasks_executed: list[str] = Field(default_factory=list)
    tools_invoked: list[str] = Field(default_factory=list)
    handoffs: list[str] = Field(default_factory=list)
    start_time: str
    end_time: str | None = None
    execution_time_seconds: float | None = None
    errors: list[WorkflowError] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)
    revision_count: int = 0
    final_status: str = "in_progress"
