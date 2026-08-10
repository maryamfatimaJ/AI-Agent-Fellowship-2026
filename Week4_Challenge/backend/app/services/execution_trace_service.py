"""Compiles the ExecutionTrace summary (Run ID, agents, tasks, tools,
handoffs, errors, approvals, revision count, timing, final status) from the
accumulated graph-state fields — never from chain-of-thought, which is
never stored anywhere in this system."""

from __future__ import annotations

from app.schemas.execution import ExecutionLogEntry, ExecutionTrace, WorkflowError
from app.utils.time_utils import elapsed_seconds, utc_now
from datetime import datetime


def compile_execution_trace(run_id: str, values: dict) -> ExecutionTrace:
    execution_log: list[ExecutionLogEntry] = values.get("execution_log", [])
    errors: list[WorkflowError] = values.get("errors", [])

    agents_invoked = list(dict.fromkeys(entry.agent for entry in execution_log))
    tools_invoked = list(dict.fromkeys(entry.tool for entry in execution_log if entry.tool))
    approvals = [entry.message for entry in execution_log if entry.agent == "human"]

    workflow_status = values.get("workflow_status", "in_progress")
    started_at = values.get("started_at")
    updated_at = values.get("updated_at")

    execution_time = None
    if started_at:
        end_reference = updated_at or started_at
        try:
            execution_time = elapsed_seconds(
                datetime.fromisoformat(started_at), datetime.fromisoformat(end_reference)
            )
        except ValueError:
            execution_time = None

    is_terminal = workflow_status in {"completed", "rejected", "failed"}

    return ExecutionTrace(
        run_id=run_id,
        user_request=values.get("user_request", ""),
        agents_invoked=agents_invoked,
        tasks_executed=values.get("completed_tasks", []),
        tools_invoked=tools_invoked,
        handoffs=values.get("handoffs", []),
        start_time=started_at or utc_now().isoformat(),
        end_time=updated_at if is_terminal else None,
        execution_time_seconds=execution_time,
        errors=errors,
        approvals=approvals,
        revision_count=values.get("revision_count", 0),
        final_status=workflow_status,
    )
