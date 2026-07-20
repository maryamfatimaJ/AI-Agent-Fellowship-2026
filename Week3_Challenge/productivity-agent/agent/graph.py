"""
agent/graph.py
-----------------
The agent controller — this is the loop Requirement 5 describes: decide
whether a tool is needed, which one, whether approval is required,
whether the result is enough, and when to stop. Requirement 9's limits
(max steps, duplicate-call detection, loop prevention) are enforced
here too, since they're really properties of this loop, not of any
individual tool.
"""

import json
from datetime import datetime, timezone

from config import settings
from tools.registry import get_tool
from agent.state import AgentResult, StepRecord, PendingApproval
from agent.nodes import decide_next_action, execute_tool_with_limits, DecisionError, ToolExecutionError
from logging_.run_logger import log_agent_run
from agent import memory


def run_agent(user_request, session_id, already_approved=None):
    """
    Public entry point: times the run, saves an execution log
    (Requirement 10), and records the conversation turn in session
    memory (Requirement 11) around the actual agent loop in
    _run_agent_loop().
    """
    start_time = datetime.now(timezone.utc)

    result = _run_agent_loop(user_request, session_id, already_approved)

    end_time = datetime.now(timezone.utc)

    if already_approved is not None:
        approval_status = "approved_and_executed"
    elif result.pending_approval is not None:
        approval_status = "awaiting_approval"
    else:
        approval_status = "not_required"

    # Saving the execution log and updating session memory are both
    # "best effort" — a database problem here (Requirement 8: database
    # failure) should never destroy a result the agent already
    # produced successfully. Failures here are reported to the server
    # console for debugging, not shown to the user or allowed to crash
    # the request.
    try:
        log_agent_run(user_request, result, start_time, end_time, approval_status)
    except Exception as logging_error:
        print("Warning: failed to save execution log:", logging_error)

    try:
        # Record this turn in session memory, so future messages in this
        # session can refer back to it ("the second one", etc.).
        memory.add_message(session_id, "user", user_request)
        if result.final_response:
            memory.add_message(session_id, "agent", result.final_response)
        elif result.error:
            memory.add_message(session_id, "agent", "Error: " + result.error)
        elif result.pending_approval:
            memory.add_message(session_id, "agent", "Proposed: " + result.pending_approval.title)
    except Exception as memory_error:
        print("Warning: failed to update session memory:", memory_error)

    return result


def _run_agent_loop(user_request, session_id, already_approved=None):
    """
    Run the agent on one user request.

    If `already_approved` is given (a dict with "tool_name" and
    "tool_arguments"), that tool is executed immediately first — this
    is how app.py resumes a run after the user clicks Approve on a
    previously-proposed action — and the loop then continues from there
    to see if the agent has enough to answer yet.
    """
    steps = []
    prior_tool_results = []
    calls_made_this_run = set()  # for duplicate-call detection
    create_task_calls_this_run = 0  # for forcing approval on a second create_task call (Requirement 7)

    session_memory = memory.get_session_memory(session_id)

    if already_approved is not None:
        tool_name = already_approved["tool_name"]
        tool_arguments = already_approved["tool_arguments"]

        steps.append(StepRecord(stage="executing", detail="Executing approved action: " + tool_name, tool_name=tool_name, tool_arguments=tool_arguments))
        try:
            result = execute_tool_with_limits(tool_name, tool_arguments)
        except ToolExecutionError as error:
            steps.append(StepRecord(stage="error", detail=str(error)))
            return AgentResult(error=str(error), steps=steps)

        steps.append(StepRecord(stage="done", detail="'" + tool_name + "' completed successfully.",
                                 tool_name=tool_name, tool_result=str(result)))
        prior_tool_results.append({"tool_name": tool_name, "result": str(result)})
        calls_made_this_run.add(_call_signature(tool_name, tool_arguments))
        memory.set_last_tool_result(session_id, tool_name, result)

    # ============================================================
    # MAIN DECISION LOOP
    # ============================================================

    for step_number in range(1, settings.MAX_AGENT_STEPS + 1):
        steps.append(StepRecord(stage="thinking", detail="Interpreting the request."))

        try:
            decision = decide_next_action(
                user_request, prior_tool_results,
                conversation_history=session_memory.messages,
                last_shown_tasks=session_memory.last_shown_tasks,
                preferences=session_memory.preferences,
                last_tool_result=session_memory.last_tool_result,
                current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            )
        except DecisionError as error:
            steps.append(StepRecord(stage="error", detail=str(error)))
            return AgentResult(error=str(error), steps=steps)

        # Requirement 11: notice and remember a stated preference, if any.
        if decision.user_preference:
            memory.add_preference(session_id, decision.user_preference)

        # --- Direct answer: stop here ---
        if decision.action == "answer":
            steps.append(StepRecord(stage="done", detail=decision.reasoning_summary or "Answer ready."))
            return AgentResult(final_response=decision.answer, steps=steps)

        # --- Needs clarification from the user: stop here ---
        if decision.action == "ask_clarification":
            steps.append(StepRecord(stage="done", detail="Asking the user for clarification."))
            return AgentResult(final_response=decision.clarification_question, steps=steps)

        # --- Wants to call a tool ---
        tool_name = decision.tool_name
        tool_arguments = decision.tool_arguments or {}

        steps.append(StepRecord(
            stage="selecting_tool",
            detail=decision.reasoning_summary or ("Selecting tool: " + str(tool_name)),
            tool_name=tool_name,
            tool_arguments=tool_arguments,
        ))

        # Loop prevention: refuse to call the exact same tool with the
        # exact same arguments twice in one run (Requirement 9).
        signature = _call_signature(tool_name, tool_arguments)
        if signature in calls_made_this_run:
            error_message = "Stopped to avoid repeating the same '" + str(tool_name) + "' call again with identical arguments."
            steps.append(StepRecord(stage="error", detail=error_message))
            return AgentResult(error=error_message, steps=steps)

        tool_def = get_tool(tool_name)
        if tool_def is None:
            error_message = "The agent tried to use an unsupported tool: '" + str(tool_name) + "'."
            steps.append(StepRecord(stage="error", detail=error_message))
            return AgentResult(error=error_message, steps=steps)

        # --- Approval gate ---
        # Requirement 7 requires approval before "creating multiple tasks."
        # A single create_task call doesn't need approval, but if the
        # agent calls it a SECOND time in the same run, that's exactly
        # the multi-task-creation case — so approval is forced here at
        # the code level, not left to the LLM to remember on its own.
        needs_approval = tool_def.requires_approval
        if tool_name == "create_task" and create_task_calls_this_run >= 1:
            needs_approval = True

        if needs_approval:
            steps.append(StepRecord(stage="waiting_approval", detail="Waiting for approval to run '" + tool_name + "'."))
            pending = PendingApproval(
                tool_name=tool_name,
                tool_arguments=tool_arguments,
                title=_build_approval_title(tool_name),
                description=tool_def.description,
            )
            return AgentResult(pending_approval=pending, steps=steps)

        # --- Execute the tool (with its own timeout/retry handling) ---
        steps.append(StepRecord(stage="executing", detail="Executing '" + tool_name + "'.", tool_name=tool_name, tool_arguments=tool_arguments))
        try:
            result = execute_tool_with_limits(tool_name, tool_arguments)
        except ToolExecutionError as error:
            steps.append(StepRecord(stage="error", detail=str(error)))
            return AgentResult(error=str(error), steps=steps)

        calls_made_this_run.add(signature)
        if tool_name == "create_task":
            create_task_calls_this_run += 1
        prior_tool_results.append({"tool_name": tool_name, "result": str(result)})
        memory.set_last_tool_result(session_id, tool_name, result)
        steps.append(StepRecord(
            stage="done", detail="'" + tool_name + "' completed.", tool_name=tool_name, tool_result=str(result)
        ))

        # Requirement 11: remember exactly which tasks were just shown,
        # in order, so a follow-up like "mark the second one complete"
        # can be resolved to a real task_id later.
        if tool_name == "list_tasks" and hasattr(result, "tasks"):
            task_snapshots = [
                {"task_id": task.task_id, "title": task.title, "status": task.status.value, "priority": task.priority.value}
                for task in result.tasks
            ]
            memory.set_last_shown_tasks(session_id, task_snapshots)

        # Loop back — the agent will now decide whether this result is
        # enough to answer, or whether another tool call is needed.

    # If we fall out of the loop, MAX_AGENT_STEPS was reached without a final answer.
    error_message = "Stopped after reaching the maximum of " + str(settings.MAX_AGENT_STEPS) + " steps without a final answer."
    steps.append(StepRecord(stage="error", detail=error_message))
    return AgentResult(error=error_message, steps=steps)


def _call_signature(tool_name, tool_arguments):
    """A stable string identifying one specific tool call, for duplicate detection."""
    return str(tool_name) + ":" + json.dumps(tool_arguments, sort_keys=True, default=str)


def _build_approval_title(tool_name):
    """A short, human-readable title for the approval card."""
    titles = {
        "update_task": "Update this task?",
        "complete_task": "Mark this task as complete?",
        "create_task": "Create these tasks?",
        "create_tasks_bulk": "Create these tasks?",
        "create_reminder": "Create this reminder?",
        "draft_follow_up_email": "Send this follow-up email?",
    }
    return titles.get(tool_name, "Run '" + tool_name + "'?")
