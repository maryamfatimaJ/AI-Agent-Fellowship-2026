"""
schemas.py
----------
Pydantic schemas used to validate data at the boundaries of the app —
what a tool receives as input, and what it hands back as output. These
are intentionally separate from database/models.py (the SQLAlchemy
storage models): a tool's input might omit fields the database fills
in automatically (like task_id or created_date), and a tool's output
might include computed fields the database doesn't store at all.
"""

from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, field_validator

from database.models import Priority, Status

# A small set of common relative-date words the LLM occasionally passes
# through literally (e.g. due_date="tomorrow") instead of converting to
# an absolute date itself. The primary fix is prompt-level — see the
# DATES IN TOOL ARGUMENTS section in agent/prompts.py, which tells the
# LLM the current date and asks it to convert these itself — this is
# just a safety net for when it doesn't, so a request like "create a
# task due tomorrow" still succeeds instead of failing with a raw
# Pydantic parsing error.
_RELATIVE_DATE_OFFSETS = {"today": 0, "tomorrow": 1, "yesterday": -1}


def _coerce_relative_date(value):
    """If `value` is one of the words above, turn it into a real UTC datetime; otherwise pass it through unchanged."""
    if isinstance(value, str) and value.strip().lower() in _RELATIVE_DATE_OFFSETS:
        offset_days = _RELATIVE_DATE_OFFSETS[value.strip().lower()]
        target_date = datetime.now(timezone.utc).date() + timedelta(days=offset_days)
        return datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    return value


# ============================================================
# TASK SCHEMAS
# ============================================================

class TaskCreate(BaseModel):
    """What's required to create a new task (Tool 1: Create Task)."""

    title: str = Field(..., min_length=1, description="Short task title")
    description: str = Field(default="", description="Longer task description")
    priority: Priority = Field(default=Priority.MEDIUM)
    due_date: datetime | None = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    source: str = Field(default="user", description="Where this task came from, e.g. 'user' or 'meeting_notes'")
    notes: str = Field(default="", description="Free-text notes/comments on the task itself")

    _coerce_due_date = field_validator("due_date", mode="before")(_coerce_relative_date)


class TaskUpdate(BaseModel):
    """
    What can change on an existing task (Tool 3: Update Task).
    task_id says WHICH task; every other field is optional, since an
    update might only touch one of them.
    """

    task_id: str
    title: str | None = None
    description: str | None = None
    priority: Priority | None = None
    due_date: datetime | None = None
    status: Status | None = None
    tags: list[str] | None = None
    notes: str | None = None

    _coerce_due_date = field_validator("due_date", mode="before")(_coerce_relative_date)


class TaskOut(BaseModel):
    """The shape of a task returned back to the agent or the UI."""

    task_id: str
    title: str
    description: str
    priority: Priority
    status: Status
    due_date: datetime | None
    created_date: datetime
    updated_date: datetime
    tags: list[str]
    source: str
    notes: str

    model_config = {"from_attributes": True}  # lets this be built directly from a Task ORM object


# ============================================================
# NOTE SCHEMAS
# ============================================================

class NoteCreate(BaseModel):
    """What's required to save a new note (Tool 6: Save Note)."""

    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    category: str = Field(default="general")
    tags: list[str] = Field(default_factory=list)


class NoteUpdate(BaseModel):
    """
    What can change on an existing note. note_id says WHICH note; every
    other field is optional, since an update might only touch one of them.
    """

    note_id: str
    title: str | None = None
    content: str | None = None
    category: str | None = None
    tags: list[str] | None = None


class NoteOut(BaseModel):
    """The shape of a note returned back to the agent or the UI."""

    note_id: str
    title: str
    content: str
    category: str
    tags: list[str]
    created_date: datetime
    updated_date: datetime

    model_config = {"from_attributes": True}


# ============================================================
# TOOL SCHEMAS
# ------------------------------------------------------------
# One Input/Output schema pair per tool. Keeping these separate from
# TaskCreate/TaskUpdate above (even though some overlap) means a tool's
# input shape can evolve — e.g. adding a confirmation flag — without
# touching the core Task validation schemas used elsewhere.
# ============================================================

# --- Tool 1: Create Task (bulk variant, for Workflow A) ---

class BulkCreateTasksInput(BaseModel):
    tasks: list[TaskCreate] = Field(..., min_length=1)


class BulkCreateTasksOutput(BaseModel):
    created_tasks: list[TaskOut]
    task_ids: list[str]


# --- Tool 2: List Tasks ---

class ListTasksInput(BaseModel):
    status: Status | None = None
    priority: Priority | None = None
    tag: str | None = None
    due_before: datetime | None = Field(default=None, description="Only include tasks due on or before this date (e.g. for 'due this week')")

    _coerce_due_before = field_validator("due_before", mode="before")(_coerce_relative_date)


class ListTasksOutput(BaseModel):
    tasks: list[TaskOut]
    total_count: int


# --- Tool 4: Complete Task ---

class CompleteTaskInput(BaseModel):
    task_id: str


class CompleteTaskOutput(BaseModel):
    task_id: str
    status: Status
    completed_at: datetime


# --- Tool 5: Search Notes ---

class SearchNotesInput(BaseModel):
    query: str = Field(..., min_length=1)
    category: str | None = None
    date_from: datetime | None = Field(default=None, description="Only include notes created on or after this date")
    date_to: datetime | None = Field(default=None, description="Only include notes created on or before this date")

    _coerce_dates = field_validator("date_from", "date_to", mode="before")(_coerce_relative_date)


class NoteSearchResult(BaseModel):
    note: NoteOut
    match_score: float  # 0.0-1.0, higher = better match


class SearchNotesOutput(BaseModel):
    results: list[NoteSearchResult]


# --- Tool 7: Extract Meeting Actions ---

class ActionItem(BaseModel):
    description: str
    owner: str | None = None
    deadline: str | None = None


class ExtractMeetingActionsInput(BaseModel):
    transcript: str = Field(..., min_length=1)


class ExtractMeetingActionsOutput(BaseModel):
    summary: str
    decisions: list[str]
    action_items: list[ActionItem]
    unresolved_questions: list[str]


# --- Tool 8: Generate Work Plan ---

class GenerateWorkPlanInput(BaseModel):
    available_hours: float = Field(..., gt=0)
    date: str  # ISO date string, e.g. "2026-07-20"
    user_priorities: list[str] = Field(default_factory=list)


class ScheduledTask(BaseModel):
    task_id: str
    title: str
    estimated_hours: float
    reason: str  # short explanation of why it's scheduled here


class GenerateWorkPlanOutput(BaseModel):
    ordered_schedule: list[ScheduledTask]
    recommended_focus_areas: list[str]
    deferred_tasks: list[TaskOut]
    risk_warnings: list[str]


# --- Bonus tool: Detect Overdue Tasks ---

class DetectOverdueTasksOutput(BaseModel):
    overdue_tasks: list[TaskOut]
    count: int


# --- Bonus tool: Create Reminder ---

class ReminderCreate(BaseModel):
    message: str = Field(..., min_length=1)
    remind_at: datetime
    task_id: str | None = Field(default=None, description="Task this reminder relates to, if any")

    _coerce_remind_at = field_validator("remind_at", mode="before")(_coerce_relative_date)


class ReminderOut(BaseModel):
    reminder_id: str
    message: str
    remind_at: datetime
    task_id: str | None
    created_date: datetime

    model_config = {"from_attributes": True}


# --- Bonus tool: Draft Follow-up Email ---

class DraftFollowUpEmailInput(BaseModel):
    recipient: str = Field(..., min_length=1)
    context: str = Field(..., min_length=1, description="What this follow-up is about")
    task_id: str | None = Field(default=None, description="Related task to pull extra context from, if any")


class DraftFollowUpEmailOutput(BaseModel):
    recipient: str
    subject: str
    body: str


# ============================================================
# EXECUTION LOG SCHEMA (Requirement 10)
# ============================================================

class ExecutionLogOut(BaseModel):
    run_id: str
    user_request: str
    selected_model: str
    tools_called: list[str]
    tool_arguments: list
    tool_results: list
    approval_status: str
    error: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    final_outcome: str

    model_config = {"from_attributes": True}

