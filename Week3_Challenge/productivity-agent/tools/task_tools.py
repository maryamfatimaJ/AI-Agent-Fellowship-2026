"""
tools/task_tools.py
---------------------
Task-related tools the agent can call. Every function here does exactly
one thing, validates its input with a Pydantic schema, and returns a
Pydantic output schema — never a raw dict. The `requires_approval` flag
next to each tool is metadata the agent controller reads later (Phase 4)
to decide whether to show an approval card before running it.
"""

from datetime import datetime, timezone

from database import repository
from database.models import Priority, Status
from tools.logging_setup import get_tool_logger
from schemas import (
    TaskCreate, TaskUpdate, TaskOut,
    BulkCreateTasksInput, BulkCreateTasksOutput,
    ListTasksInput, ListTasksOutput,
    CompleteTaskInput, CompleteTaskOutput,
    DetectOverdueTasksOutput,
)

logger = get_tool_logger("task_tools")


class ToolError(Exception):
    """Raised when a tool can't complete because of bad input or a missing record."""
    pass


# ============================================================
# TOOL 1: CREATE TASK
# ============================================================

TASK_1_REQUIRES_APPROVAL = False  # creating one task is low-risk; multiple at once do need approval (Requirement 7)


def create_task(data: TaskCreate) -> TaskOut:
    """Create a new task and return it."""
    logger.info("create_task called: title=%r priority=%s", data.title, data.priority.value)
    task = repository.create_task(data)
    logger.info("create_task succeeded: task_id=%s", task.task_id)
    return task


# ============================================================
# TOOL 1 (BULK VARIANT): CREATE MULTIPLE TASKS AT ONCE
# ------------------------------------------------------------
# Used for Workflow A (meeting notes -> tasks), where several tasks are
# proposed together. Requirement 7 explicitly requires approval before
# "creating multiple tasks" — this tool is how the agent is meant to do
# that in one approved batch, instead of calling create_task repeatedly.
# ============================================================

TASK_1_BULK_REQUIRES_APPROVAL = True


def create_tasks_bulk(data: BulkCreateTasksInput) -> BulkCreateTasksOutput:
    """Create several tasks at once and return all of them, including their new IDs."""
    logger.info("create_tasks_bulk called: count=%d", len(data.tasks))
    created = [repository.create_task(task_spec) for task_spec in data.tasks]
    logger.info("create_tasks_bulk succeeded: task_ids=%s", [task.task_id for task in created])
    return BulkCreateTasksOutput(created_tasks=created, task_ids=[task.task_id for task in created])


# ============================================================
# TOOL 2: LIST TASKS
# ============================================================

TASK_2_REQUIRES_APPROVAL = False  # read-only, never needs approval


def list_tasks(data: ListTasksInput) -> ListTasksOutput:
    """Return tasks matching the given filters, plus how many matched."""
    logger.info(
        "list_tasks called: status=%s priority=%s tag=%s due_before=%s",
        data.status, data.priority, data.tag, data.due_before,
    )
    tasks = repository.list_tasks(status=data.status, priority=data.priority, tag=data.tag, due_before=data.due_before)
    logger.info("list_tasks returned %d task(s)", len(tasks))
    return ListTasksOutput(tasks=tasks, total_count=len(tasks))


# ============================================================
# TOOL 3: UPDATE TASK
# ============================================================

TASK_3_REQUIRES_APPROVAL = True  # this is a write action (Requirement 4)


def update_task(data: TaskUpdate) -> TaskOut:
    """Apply changes to an existing task. Raises ToolError if the task doesn't exist."""
    logger.info("update_task called: task_id=%s", data.task_id)
    updated = repository.update_task(data.task_id, data)
    if updated is None:
        logger.error("update_task failed: no task found with ID %s", data.task_id)
        raise ToolError(f"No task found with ID '{data.task_id}'.")
    logger.info("update_task succeeded: task_id=%s", data.task_id)
    return updated


# ============================================================
# TOOL 4: COMPLETE TASK
# ============================================================

TASK_4_REQUIRES_APPROVAL = True  # explicitly required by Requirement 4 and Requirement 7


def complete_task(data: CompleteTaskInput) -> CompleteTaskOutput:
    """Mark a task as Completed. Raises ToolError if the task doesn't exist."""
    logger.info("complete_task called: task_id=%s", data.task_id)
    updated = repository.complete_task(data.task_id)
    if updated is None:
        logger.error("complete_task failed: no task found with ID %s", data.task_id)
        raise ToolError(f"No task found with ID '{data.task_id}'.")

    logger.info("complete_task succeeded: task_id=%s", data.task_id)
    return CompleteTaskOutput(
        task_id=updated.task_id,
        status=updated.status,
        completed_at=updated.updated_date,
    )


# ============================================================
# BONUS TOOL: DETECT OVERDUE TASKS
# ============================================================

BONUS_DETECT_OVERDUE_REQUIRES_APPROVAL = False  # read-only


def detect_overdue_tasks() -> DetectOverdueTasksOutput:
    """
    Find every task that has a due date in the past and isn't already
    Completed or Cancelled.
    """
    logger.info("detect_overdue_tasks called")
    now = datetime.now(timezone.utc)
    all_tasks = repository.list_tasks()

    overdue = [
        task for task in all_tasks
        if task.due_date is not None
        and _as_aware_utc(task.due_date) < now
        and task.status not in (Status.COMPLETED, Status.CANCELLED)
    ]

    logger.info("detect_overdue_tasks found %d overdue task(s)", len(overdue))
    return DetectOverdueTasksOutput(overdue_tasks=overdue, count=len(overdue))


def _as_aware_utc(value: datetime) -> datetime:
    """Treat a naive datetime (no timezone info) as UTC, so comparisons never crash."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# ============================================================
# EFFORT HEURISTIC — used by generate_work_plan (tools/planning_tools.py)
# ============================================================

# Simple, transparent effort heuristic — no LLM call needed, so it's
# fast, free, and fully predictable. Priority alone is a rough proxy
# for how much attention a task usually needs.
_EFFORT_HOURS_BY_PRIORITY = {
    Priority.LOW: 1.0,
    Priority.MEDIUM: 2.0,
    Priority.HIGH: 4.0,
    Priority.CRITICAL: 6.0,
}
