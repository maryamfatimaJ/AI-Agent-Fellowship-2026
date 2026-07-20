"""
tests/test_tool_logging.py
-----------------------------
Confirms each tool logs its own invocation and outcome (Requirement 4:
"Logging"), independent of whatever calls it. Uses pytest's caplog
fixture to capture real log records, not just check that a logger
object exists.
"""

import os
import tempfile
import logging

import pytest

_temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = "sqlite:///" + _temp_db_file.name
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("SECRET_KEY", "test-secret-not-real")

from database import repository
from schemas import (
    TaskCreate, TaskUpdate, ListTasksInput, CompleteTaskInput,
    NoteCreate, SearchNotesInput, GenerateWorkPlanInput,
)
from tools import task_tools, note_tools, planning_tools


@pytest.fixture(autouse=True)
def fresh_database():
    repository.reset_db()
    yield


def test_create_task_logs_invocation_and_success(caplog):
    with caplog.at_level(logging.INFO, logger="tools"):
        task_tools.create_task(TaskCreate(title="Logged task"))

    assert any("create_task called" in record.message for record in caplog.records)
    assert any("create_task succeeded" in record.message for record in caplog.records)


def test_update_task_logs_error_for_unknown_id(caplog):
    with caplog.at_level(logging.INFO, logger="tools"):
        with pytest.raises(task_tools.ToolError):
            task_tools.update_task(TaskUpdate(task_id="does-not-exist", title="New"))

    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert any("update_task failed" in r.message for r in error_records)


def test_complete_task_logs_error_for_unknown_id(caplog):
    with caplog.at_level(logging.INFO, logger="tools"):
        with pytest.raises(task_tools.ToolError):
            task_tools.complete_task(CompleteTaskInput(task_id="does-not-exist"))

    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert any("complete_task failed" in r.message for r in error_records)


def test_list_tasks_logs_result_count(caplog):
    task_tools.create_task(TaskCreate(title="A"))
    task_tools.create_task(TaskCreate(title="B"))

    with caplog.at_level(logging.INFO, logger="tools"):
        task_tools.list_tasks(ListTasksInput())

    assert any("list_tasks returned 2 task(s)" in record.message for record in caplog.records)


def test_save_note_logs_invocation_and_success(caplog):
    with caplog.at_level(logging.INFO, logger="tools"):
        note_tools.save_note(NoteCreate(title="Logged note", content="Some content"))

    assert any("save_note called" in record.message for record in caplog.records)
    assert any("save_note succeeded" in record.message for record in caplog.records)


def test_search_notes_logs_result_count(caplog):
    note_tools.save_note(NoteCreate(title="Marketing plan", content="Details"))

    with caplog.at_level(logging.INFO, logger="tools"):
        note_tools.search_notes(SearchNotesInput(query="marketing"))

    assert any("search_notes returned 1 result(s)" in record.message for record in caplog.records)


def test_generate_work_plan_logs_invocation(caplog):
    task_tools.create_task(TaskCreate(title="Some task"))

    with caplog.at_level(logging.INFO, logger="tools"):
        planning_tools.generate_work_plan(GenerateWorkPlanInput(available_hours=8, date="2026-07-20"))

    assert any("generate_work_plan called" in record.message for record in caplog.records)
    assert any("generate_work_plan succeeded" in record.message for record in caplog.records)


def test_extract_meeting_actions_logs_llm_error(monkeypatch, caplog):
    from services.llm_service import LLMError

    def broken_generate_json(prompt):
        raise LLMError("simulated LLM failure")

    monkeypatch.setattr(planning_tools, "generate_json", broken_generate_json)

    from schemas import ExtractMeetingActionsInput

    with caplog.at_level(logging.INFO, logger="tools"):
        with pytest.raises(task_tools.ToolError):
            planning_tools.extract_meeting_actions(ExtractMeetingActionsInput(transcript="Some text"))

    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert any("extract_meeting_actions failed" in r.message for r in error_records)
