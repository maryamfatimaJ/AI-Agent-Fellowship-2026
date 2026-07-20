"""
tests/test_repository.py
--------------------------
Tests for database/repository.py, using a temporary SQLite file as the
database instead of the real one. A temp FILE (not sqlite:///:memory:)
is used deliberately — an in-memory SQLite database is actually a
separate, empty database on every new connection unless you configure
a shared connection pool, which is an easy mistake to make. A temp file
avoids that gotcha entirely.

Run with:
    pytest tests/test_repository.py
"""

import os
import tempfile

import pytest

# The DATABASE_URL environment variable must be set BEFORE config.py
# and repository.py are imported, since repository.py builds its
# database engine once, at import time.
_temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = "sqlite:///" + _temp_db_file.name
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("SECRET_KEY", "test-secret-not-real")

from database import repository
from database.models import Priority, Status
from schemas import TaskCreate, TaskUpdate, NoteCreate


@pytest.fixture(autouse=True)
def fresh_database():
    """Wipe and recreate all tables before every test, so tests never affect each other."""
    repository.reset_db()
    yield


# ============================================================
# TASK TESTS
# ============================================================

def test_create_task_returns_expected_fields():
    task = repository.create_task(TaskCreate(title="Write report", priority=Priority.HIGH))

    assert task.title == "Write report"
    assert task.priority == Priority.HIGH
    assert task.status == Status.PENDING  # default status for a brand-new task
    assert task.task_id != ""


def test_get_task_finds_an_existing_task():
    created = repository.create_task(TaskCreate(title="Review PR"))
    found = repository.get_task(created.task_id)

    assert found is not None
    assert found.task_id == created.task_id


def test_get_task_returns_none_for_unknown_id():
    result = repository.get_task("this-id-does-not-exist")
    assert result is None


def test_list_tasks_filters_by_status():
    repository.create_task(TaskCreate(title="Task A"))
    completed_task = repository.create_task(TaskCreate(title="Task B"))
    repository.complete_task(completed_task.task_id)

    pending_tasks = repository.list_tasks(status=Status.PENDING)
    completed_tasks = repository.list_tasks(status=Status.COMPLETED)

    assert any(task.title == "Task A" for task in pending_tasks)
    assert any(task.title == "Task B" for task in completed_tasks)
    assert all(task.status == Status.COMPLETED for task in completed_tasks)


def test_update_task_only_changes_given_fields():
    task = repository.create_task(TaskCreate(title="Original title", priority=Priority.LOW))

    updated = repository.update_task(task.task_id, TaskUpdate(task_id=task.task_id, priority=Priority.CRITICAL))

    assert updated.title == "Original title"  # unchanged
    assert updated.priority == Priority.CRITICAL  # changed


def test_complete_task_sets_status_to_completed():
    task = repository.create_task(TaskCreate(title="Finish this"))
    completed = repository.complete_task(task.task_id)

    assert completed.status == Status.COMPLETED


def test_delete_task_removes_it():
    task = repository.create_task(TaskCreate(title="Temporary task"))

    was_deleted = repository.delete_task(task.task_id)
    still_there = repository.get_task(task.task_id)

    assert was_deleted is True
    assert still_there is None


def test_tags_round_trip_correctly():
    """Tags go in as a list, get stored as a string, and must come back out as a list."""
    task = repository.create_task(TaskCreate(title="Tagged task", tags=["urgent", "client-facing"]))

    assert task.tags == ["urgent", "client-facing"]


# ============================================================
# NOTE TESTS
# ============================================================

def test_create_and_search_notes():
    repository.create_note(NoteCreate(title="Marketing sync", content="Discussed the new campaign launch"))
    repository.create_note(NoteCreate(title="Unrelated note", content="Grocery list"))

    results = repository.search_notes("campaign")

    assert len(results) == 1
    assert results[0].title == "Marketing sync"


def test_search_notes_with_no_matches_returns_empty_list():
    repository.create_note(NoteCreate(title="Some note", content="Some content"))

    results = repository.search_notes("nonexistent-keyword-xyz")

    assert results == []
