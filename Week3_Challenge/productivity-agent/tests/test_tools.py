"""
tests/test_tools.py
----------------------
Tests for tools/task_tools.py, tools/note_tools.py, and
tools/planning_tools.py.

The LLM-dependent tool (extract_meeting_actions) is tested with a
mocked response instead of a real Gemini call — tests should be fast,
free, and not fail just because of a network hiccup or rate limit.
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

_temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = "sqlite:///" + _temp_db_file.name
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("SECRET_KEY", "test-secret-not-real")

from database import repository
from database.models import Priority, Status
from schemas import (
    TaskCreate, TaskUpdate, ListTasksInput, CompleteTaskInput,
    NoteCreate, SearchNotesInput,
    ExtractMeetingActionsInput, GenerateWorkPlanInput,
    ReminderCreate, DraftFollowUpEmailInput,
)
from tools import task_tools, note_tools, planning_tools, reminder_tools, email_tools


@pytest.fixture(autouse=True)
def fresh_database():
    repository.reset_db()
    yield


# ============================================================
# TOOL 1-4: TASK TOOLS
# ============================================================

def test_create_task_tool():
    task = task_tools.create_task(TaskCreate(title="Write tests"))
    assert task.title == "Write tests"
    assert task.status == Status.PENDING


def test_create_tasks_bulk_creates_all_and_returns_ids():
    from schemas import BulkCreateTasksInput

    result = task_tools.create_tasks_bulk(BulkCreateTasksInput(tasks=[
        TaskCreate(title="Task from meeting 1"),
        TaskCreate(title="Task from meeting 2"),
    ]))

    assert len(result.created_tasks) == 2
    assert len(result.task_ids) == 2
    assert result.created_tasks[0].task_id == result.task_ids[0]


def test_list_tasks_tool_returns_total_count():
    task_tools.create_task(TaskCreate(title="A", priority=Priority.HIGH))
    task_tools.create_task(TaskCreate(title="B", priority=Priority.LOW))

    result = task_tools.list_tasks(ListTasksInput(priority=Priority.HIGH))

    assert result.total_count == 1
    assert result.tasks[0].title == "A"


def test_list_tasks_tool_filters_by_due_before():
    soon = datetime.now(timezone.utc) + timedelta(days=2)
    later = datetime.now(timezone.utc) + timedelta(days=30)
    task_tools.create_task(TaskCreate(title="Due soon", due_date=soon))
    task_tools.create_task(TaskCreate(title="Due later", due_date=later))
    task_tools.create_task(TaskCreate(title="No due date"))

    cutoff = datetime.now(timezone.utc) + timedelta(days=7)
    result = task_tools.list_tasks(ListTasksInput(due_before=cutoff))

    titles = [task.title for task in result.tasks]
    assert titles == ["Due soon"]


def test_update_task_tool_raises_for_unknown_id():
    with pytest.raises(task_tools.ToolError):
        task_tools.update_task(TaskUpdate(task_id="does-not-exist", title="New title"))


def test_complete_task_tool_sets_completion_timestamp():
    task = task_tools.create_task(TaskCreate(title="Finish this"))
    result = task_tools.complete_task(CompleteTaskInput(task_id=task.task_id))

    assert result.status == Status.COMPLETED
    assert result.completed_at is not None


# ============================================================
# BONUS TOOLS
# ============================================================

def test_detect_overdue_tasks_finds_only_past_due_incomplete_tasks():
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)

    overdue_task = task_tools.create_task(TaskCreate(title="Late task", due_date=yesterday))
    task_tools.create_task(TaskCreate(title="Future task", due_date=tomorrow))
    completed_overdue = task_tools.create_task(TaskCreate(title="Late but done", due_date=yesterday))
    task_tools.complete_task(CompleteTaskInput(task_id=completed_overdue.task_id))

    result = task_tools.detect_overdue_tasks()

    overdue_ids = [task.task_id for task in result.overdue_tasks]
    assert overdue_task.task_id in overdue_ids
    assert completed_overdue.task_id not in overdue_ids  # completed tasks are never "overdue"
    assert result.count == len(result.overdue_tasks)


# ============================================================
# TOOL 5-6: NOTE TOOLS
# ============================================================

def test_save_note_tool():
    note = note_tools.save_note(NoteCreate(title="Idea", content="Try a new layout"))
    assert note.title == "Idea"


def test_search_notes_ranks_title_matches_higher():
    note_tools.save_note(NoteCreate(title="Marketing plan", content="General notes"))
    note_tools.save_note(NoteCreate(title="Random note", content="Mentions marketing briefly"))

    result = note_tools.search_notes(SearchNotesInput(query="marketing"))

    assert len(result.results) == 2
    assert result.results[0].note.title == "Marketing plan"  # title match should rank first
    assert result.results[0].match_score > result.results[1].match_score


def test_search_notes_filters_by_date_range():
    note_tools.save_note(NoteCreate(title="Marketing plan A", content="notes"))

    far_future_start = datetime.now(timezone.utc) + timedelta(days=1)
    result = note_tools.search_notes(SearchNotesInput(query="marketing", date_from=far_future_start))

    # The note was created "now", before the date_from cutoff, so it must be excluded.
    assert len(result.results) == 0


# ============================================================
# TOOL 7: EXTRACT MEETING ACTIONS (mocked LLM)
# ============================================================

def test_extract_meeting_actions_with_mocked_llm(monkeypatch):
    fake_response = {
        "summary": "The team discussed the Q3 launch.",
        "decisions": ["Launch date moved to August"],
        "action_items": [
            {"description": "Update the timeline doc", "owner": "Sara", "deadline": "Friday"}
        ],
        "unresolved_questions": ["Who owns the press release?"],
    }

    monkeypatch.setattr(planning_tools, "generate_json", lambda prompt: fake_response)

    result = planning_tools.extract_meeting_actions(
        ExtractMeetingActionsInput(transcript="Some meeting transcript text.")
    )

    assert result.summary == "The team discussed the Q3 launch."
    assert result.action_items[0].owner == "Sara"


def test_extract_meeting_actions_raises_toolerror_on_bad_llm_output(monkeypatch):
    # Missing required fields — simulates the model not following the schema.
    monkeypatch.setattr(planning_tools, "generate_json", lambda prompt: {"summary": "only this"})

    with pytest.raises(task_tools.ToolError):
        planning_tools.extract_meeting_actions(
            ExtractMeetingActionsInput(transcript="Some text.")
        )


# ============================================================
# TOOL 8: GENERATE WORK PLAN
# ============================================================

def test_generate_work_plan_prioritizes_overdue_tasks():
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    next_week = datetime.now(timezone.utc) + timedelta(days=7)

    overdue = task_tools.create_task(TaskCreate(title="Overdue thing", priority=Priority.LOW, due_date=yesterday))
    task_tools.create_task(TaskCreate(title="Future thing", priority=Priority.CRITICAL, due_date=next_week))

    plan = planning_tools.generate_work_plan(
        GenerateWorkPlanInput(available_hours=20, date="2026-07-20")
    )

    scheduled_ids = [item.task_id for item in plan.ordered_schedule]
    assert scheduled_ids[0] == overdue.task_id  # overdue beats even a lower-priority task


def test_generate_work_plan_defers_tasks_that_dont_fit():
    task_tools.create_task(TaskCreate(title="Big task", priority=Priority.CRITICAL))  # 6 hours

    plan = planning_tools.generate_work_plan(
        GenerateWorkPlanInput(available_hours=1, date="2026-07-20")
    )

    assert len(plan.ordered_schedule) == 0
    assert len(plan.deferred_tasks) == 1
    assert any("didn't fit" in warning for warning in plan.risk_warnings)


def test_generate_work_plan_defers_blocked_tasks_with_warning():
    task = task_tools.create_task(TaskCreate(title="Blocked thing"))
    task_tools.update_task(TaskUpdate(task_id=task.task_id, status=Status.BLOCKED))

    plan = planning_tools.generate_work_plan(
        GenerateWorkPlanInput(available_hours=20, date="2026-07-20")
    )

    deferred_ids = [t.task_id for t in plan.deferred_tasks]
    assert task.task_id in deferred_ids
    assert any("Blocked" in warning for warning in plan.risk_warnings)


# ============================================================
# BONUS TOOL: CREATE REMINDER
# ============================================================

def test_create_reminder_tool_persists_and_returns_id():
    remind_at = datetime.now(timezone.utc) + timedelta(days=1)
    reminder = reminder_tools.create_reminder(ReminderCreate(message="Follow up with Sara", remind_at=remind_at))

    assert reminder.reminder_id is not None
    assert reminder.message == "Follow up with Sara"


def test_create_reminder_can_reference_a_task():
    task = task_tools.create_task(TaskCreate(title="Draft report"))
    remind_at = datetime.now(timezone.utc) + timedelta(hours=2)

    reminder = reminder_tools.create_reminder(
        ReminderCreate(message="Check on the draft report", remind_at=remind_at, task_id=task.task_id)
    )

    assert reminder.task_id == task.task_id


# ============================================================
# BONUS TOOL: DRAFT FOLLOW-UP EMAIL (mocked LLM)
# ============================================================

def test_draft_follow_up_email_with_mocked_llm(monkeypatch):
    fake_response = {
        "subject": "Following up on the Q3 launch",
        "body": "Hi Sara,\n\nJust checking in on the launch timeline doc.\n\nThanks!",
    }
    monkeypatch.setattr(email_tools, "generate_json", lambda prompt: fake_response)

    result = email_tools.draft_follow_up_email(
        DraftFollowUpEmailInput(recipient="sara@example.com", context="the Q3 launch timeline doc")
    )

    assert result.recipient == "sara@example.com"
    assert result.subject == "Following up on the Q3 launch"


def test_draft_follow_up_email_raises_toolerror_on_bad_llm_output(monkeypatch):
    monkeypatch.setattr(email_tools, "generate_json", lambda prompt: {"subject": "only this"})

    with pytest.raises(task_tools.ToolError):
        email_tools.draft_follow_up_email(
            DraftFollowUpEmailInput(recipient="sara@example.com", context="the launch doc")
        )
