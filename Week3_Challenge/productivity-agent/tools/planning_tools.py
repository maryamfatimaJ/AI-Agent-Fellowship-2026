"""
tools/planning_tools.py
--------------------------
Tool 7 (Extract Meeting Actions) uses the LLM, since understanding a
free-form transcript genuinely needs language understanding.

Tool 8 (Generate Work Plan) is deliberately NOT LLM-based — scheduling
tasks by priority, deadline, and effort is a well-defined algorithm,
and keeping it deterministic means it's fast, free to run, and its
output can be tested exactly (an LLM-based scheduler would give a
slightly different answer every run, which would make automated
testing unreliable).
"""

from datetime import datetime, timezone
from pydantic import ValidationError

from database import repository
from database.models import Priority, Status
from services.llm_service import generate_json, LLMError, LLMQuotaExceededError
from tools.task_tools import _EFFORT_HOURS_BY_PRIORITY, ToolError
from tools.logging_setup import get_tool_logger

logger = get_tool_logger("planning_tools")
from schemas import (
    ExtractMeetingActionsInput, ExtractMeetingActionsOutput,
    GenerateWorkPlanInput, GenerateWorkPlanOutput, ScheduledTask,
)


# ============================================================
# TOOL 7: EXTRACT MEETING ACTIONS
# ============================================================

EXTRACT_MEETING_ACTIONS_REQUIRES_APPROVAL = False  # read-only extraction; creating tasks FROM this later does need approval

_EXTRACTION_PROMPT_TEMPLATE = """You will read a meeting transcript and extract structured information from it.

Reply with ONLY a JSON object (no other text, no markdown fences) with exactly these fields:
- "summary": a short paragraph summarizing the meeting
- "decisions": a list of strings, one per decision that was made
- "action_items": a list of objects, each with "description", "owner" (or null if not mentioned), and "deadline" (or null if not mentioned)
- "unresolved_questions": a list of strings, one per question that was raised but not answered

Do not invent information that isn't in the transcript. If a field has nothing to report, use an empty list.

Transcript:
{transcript}
"""


def extract_meeting_actions(data: ExtractMeetingActionsInput) -> ExtractMeetingActionsOutput:
    """
    Ask the LLM to pull a summary, decisions, action items, and open
    questions out of a meeting transcript, and validate that what comes
    back actually matches the required structure.
    """
    logger.info("extract_meeting_actions called: transcript_length=%d", len(data.transcript))
    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(transcript=data.transcript)

    try:
        raw_result = generate_json(prompt)
    except LLMQuotaExceededError:
        # Let this propagate as-is (not wrapped in ToolError) so
        # execute_tool_with_limits (agent/nodes.py) can recognize it and
        # skip retrying an already-exhausted daily quota.
        logger.error("extract_meeting_actions failed: Gemini quota exceeded")
        raise
    except LLMError as error:
        logger.error("extract_meeting_actions failed: LLM error: %s", error)
        raise ToolError(str(error)) from error

    try:
        result = ExtractMeetingActionsOutput.model_validate(raw_result)
        logger.info(
            "extract_meeting_actions succeeded: %d action item(s), %d decision(s)",
            len(result.action_items), len(result.decisions),
        )
        return result
    except ValidationError as error:
        # The model responded, but not in the shape we asked for —
        # this is exactly the "invalid model response" case Requirement 8
        # calls out, so it's reported clearly rather than crashing.
        logger.error("extract_meeting_actions failed: invalid model response: %s", error)
        raise ToolError(
            "The language model's response didn't match the expected structure: " + str(error)
        ) from error


# ============================================================
# TOOL 8: GENERATE WORK PLAN
# ============================================================

GENERATE_WORK_PLAN_REQUIRES_APPROVAL = False  # read-only planning; doesn't change any stored data


def generate_work_plan(data: GenerateWorkPlanInput) -> GenerateWorkPlanOutput:
    """
    Build an ordered schedule that fits inside the user's available
    hours, considering priority, due date, status, and estimated effort.

    Algorithm:
    1. Blocked tasks can't be worked on — deferred immediately, with a warning.
    2. Everything else is sorted by urgency: overdue first, then soonest
       due date, then priority as a tiebreaker.
    3. Tasks are added to the schedule in that order until the available
       hours run out; anything left over is deferred.
    """
    all_tasks = repository.list_tasks()
    now = datetime.now(timezone.utc)

    logger.info(
        "generate_work_plan called: available_hours=%s date=%s",
        data.available_hours, data.date,
    )

    active_tasks = [task for task in all_tasks if task.status not in (Status.COMPLETED, Status.CANCELLED)]
    blocked_tasks = [task for task in active_tasks if task.status == Status.BLOCKED]
    schedulable_tasks = [task for task in active_tasks if task.status != Status.BLOCKED]

    schedulable_tasks.sort(key=lambda task: _urgency_key(task, now))

    schedule: list[ScheduledTask] = []
    deferred = []
    hours_remaining = data.available_hours
    risk_warnings = []

    overdue_count = sum(1 for task in schedulable_tasks if _is_overdue(task, now))
    if overdue_count > 0:
        risk_warnings.append(f"{overdue_count} task(s) are overdue and were prioritized first.")

    if blocked_tasks:
        risk_warnings.append(f"{len(blocked_tasks)} task(s) are Blocked and can't be scheduled until unblocked.")
        deferred.extend(blocked_tasks)

    for task in schedulable_tasks:
        estimated_hours = _EFFORT_HOURS_BY_PRIORITY[task.priority]

        if estimated_hours <= hours_remaining:
            reason = _build_schedule_reason(task, now)
            schedule.append(ScheduledTask(
                task_id=task.task_id,
                title=task.title,
                estimated_hours=estimated_hours,
                reason=reason,
            ))
            hours_remaining -= estimated_hours
        else:
            deferred.append(task)

    if deferred and not blocked_tasks:
        risk_warnings.append(f"{len(deferred)} task(s) didn't fit in the available hours and were deferred.")
    elif len(deferred) > len(blocked_tasks):
        risk_warnings.append(
            f"{len(deferred) - len(blocked_tasks)} additional task(s) didn't fit and were deferred."
        )

    recommended_focus_areas = _build_focus_areas(schedule, data.user_priorities)

    logger.info(
        "generate_work_plan succeeded: %d task(s) scheduled, %d deferred",
        len(schedule), len(deferred),
    )
    return GenerateWorkPlanOutput(
        ordered_schedule=schedule,
        recommended_focus_areas=recommended_focus_areas,
        deferred_tasks=deferred,
        risk_warnings=risk_warnings,
    )


def _is_overdue(task, now: datetime) -> bool:
    if task.due_date is None:
        return False
    return _as_aware_utc(task.due_date) < now


_PRIORITY_RANK = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}


def _urgency_key(task, now: datetime) -> tuple:
    """
    Sort key: overdue tasks first, then by due date (soonest first,
    with no-due-date tasks last), then by priority as a tiebreaker.
    """
    is_overdue = 0 if _is_overdue(task, now) else 1

    if task.due_date is None:
        due_sort_value = datetime.max.replace(tzinfo=timezone.utc)
    else:
        due_sort_value = _as_aware_utc(task.due_date)

    priority_rank = _PRIORITY_RANK[task.priority]
    return (is_overdue, due_sort_value, priority_rank)


def _as_aware_utc(value: datetime) -> datetime:
    """Treat a naive datetime (no timezone info, as SQLite returns) as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _build_schedule_reason(task, now: datetime) -> str:
    if _is_overdue(task, now):
        return "Overdue — scheduled first."
    if task.due_date:
        return f"Due {task.due_date.date()}, {task.priority.value} priority."
    return f"{task.priority.value} priority, no due date."


def _build_focus_areas(schedule: list, user_priorities: list) -> list:
    focus_areas = []

    if user_priorities:
        focus_areas.append("User-stated priorities: " + ", ".join(user_priorities))

    if schedule:
        top_task = schedule[0]
        focus_areas.append("Start with \"" + top_task.title + "\" - " + top_task.reason.lower())

    if not focus_areas:
        focus_areas.append("No tasks were scheduled - the task list may be empty.")

    return focus_areas
