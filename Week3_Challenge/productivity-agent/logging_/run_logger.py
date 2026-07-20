"""
logging_/run_logger.py
-------------------------
Turns a finished agent run into a saved execution log entry. This is
the only place that decides WHAT gets logged from a run; the actual
database write lives in database/repository.py, same as everything else.
"""

from config import settings
from database import repository


def log_agent_run(user_request, result, start_time, end_time, approval_status):
    """
    Save one execution log entry for a completed run_agent() call.

    `result` is the AgentResult returned by agent/graph.py.
    `approval_status` is one of: "not_required", "awaiting_approval",
    "approved_and_executed", "rejected".
    """
    tools_called = []
    tool_arguments = []
    tool_results = []

    for step in result.steps:
        if step.stage == "executing" and step.tool_name:
            tools_called.append(step.tool_name)
            tool_arguments.append(step.tool_arguments or {})
            tool_results.append(step.tool_result)

    if result.error:
        final_outcome = "error"
    elif result.pending_approval:
        final_outcome = "awaiting_approval"
    else:
        final_outcome = "answered"

    duration_seconds = (end_time - start_time).total_seconds()

    return repository.create_execution_log(
        user_request=user_request,
        selected_model=settings.GENERATION_MODEL,
        tools_called=tools_called,
        tool_arguments=tool_arguments,
        tool_results=tool_results,
        approval_status=approval_status,
        error=result.error or "",
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration_seconds,
        final_outcome=final_outcome,
    )
