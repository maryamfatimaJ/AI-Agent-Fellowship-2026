"""
tests/test_logging.py
------------------------
Tests confirming every agent run actually gets saved as an execution
log (Requirement 10), with the right fields for each kind of outcome.
"""

import os
import tempfile

import pytest

_temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = "sqlite:///" + _temp_db_file.name
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("SECRET_KEY", "test-secret-not-real")

from database import repository
from schemas import TaskCreate
from agent import nodes, graph, memory


@pytest.fixture(autouse=True)
def fresh_database():
    repository.reset_db()
    memory._session_store.clear()
    yield


TEST_SESSION_ID = "test-session"


def _queue_decisions(monkeypatch, decisions):
    remaining = list(decisions)

    def fake_ask(prompt):
        return remaining.pop(0)

    monkeypatch.setattr(nodes, "_ask_llm_for_decision", fake_ask)


def test_direct_answer_run_is_logged_correctly(monkeypatch):
    _queue_decisions(monkeypatch, [
        {"action": "answer", "answer": "Critical is more urgent than High.", "reasoning_summary": "Answering directly."},
    ])

    graph.run_agent("What's the difference between High and Critical?", TEST_SESSION_ID)

    logs = repository.list_execution_logs()
    assert len(logs) == 1
    assert logs[0].final_outcome == "answered"
    assert logs[0].approval_status == "not_required"
    assert logs[0].tools_called == []
    assert logs[0].error == ""
    assert logs[0].duration_seconds >= 0


def test_tool_call_run_logs_the_tool_and_its_result(monkeypatch):
    repository.create_task(TaskCreate(title="Some task"))

    _queue_decisions(monkeypatch, [
        {"action": "call_tool", "tool_name": "list_tasks", "tool_arguments": {}, "reasoning_summary": "Listing tasks."},
        {"action": "answer", "answer": "You have 1 task.", "reasoning_summary": "Reporting."},
    ])

    graph.run_agent("Show me my tasks.", TEST_SESSION_ID)

    logs = repository.list_execution_logs()
    assert logs[0].tools_called == ["list_tasks"]
    assert len(logs[0].tool_arguments) == 1
    assert len(logs[0].tool_results) == 1
    assert logs[0].final_outcome == "answered"


def test_error_run_is_logged_with_error_message(monkeypatch):
    _queue_decisions(monkeypatch, [
        {"action": "call_tool", "tool_name": "not_a_real_tool", "tool_arguments": {}, "reasoning_summary": "Trying."},
    ])

    graph.run_agent("Do something unsupported.", TEST_SESSION_ID)

    logs = repository.list_execution_logs()
    assert logs[0].final_outcome == "error"
    assert "unsupported tool" in logs[0].error.lower()


def test_pending_approval_run_logs_awaiting_approval_status(monkeypatch):
    task = repository.create_task(TaskCreate(title="Finish the report"))

    _queue_decisions(monkeypatch, [
        {"action": "call_tool", "tool_name": "complete_task", "tool_arguments": {"task_id": task.task_id}, "reasoning_summary": "Completing."},
    ])

    graph.run_agent("Mark the report as done.", TEST_SESSION_ID)

    logs = repository.list_execution_logs()
    assert logs[0].final_outcome == "awaiting_approval"
    assert logs[0].approval_status == "awaiting_approval"


def test_resumed_run_after_approval_logs_approved_and_executed(monkeypatch):
    task = repository.create_task(TaskCreate(title="Finish the report"))

    _queue_decisions(monkeypatch, [
        {"action": "answer", "answer": "Done.", "reasoning_summary": "Confirming."},
    ])

    graph.run_agent(
        "Mark the report as done.",
        TEST_SESSION_ID,
        already_approved={"tool_name": "complete_task", "tool_arguments": {"task_id": task.task_id}},
    )

    logs = repository.list_execution_logs()
    assert logs[0].approval_status == "approved_and_executed"
    assert logs[0].tools_called == ["complete_task"]


def test_list_execution_logs_returns_newest_first(monkeypatch):
    _queue_decisions(monkeypatch, [
        {"action": "answer", "answer": "First answer.", "reasoning_summary": "..."},
        {"action": "answer", "answer": "Second answer.", "reasoning_summary": "..."},
    ])

    graph.run_agent("First request", TEST_SESSION_ID)
    graph.run_agent("Second request", TEST_SESSION_ID)

    logs = repository.list_execution_logs()
    assert len(logs) == 2
    assert logs[0].user_request == "Second request"  # most recent first


def test_logging_failure_does_not_destroy_a_successful_result(monkeypatch):
    """
    Requirement 8: a database failure must be handled gracefully. If
    saving the execution log fails for any reason, the user should
    still get the answer the agent actually produced, not a crash.
    """
    _queue_decisions(monkeypatch, [
        {"action": "answer", "answer": "Here's your answer.", "reasoning_summary": "..."},
    ])

    def broken_log_agent_run(*args, **kwargs):
        raise RuntimeError("Simulated database failure while logging.")

    monkeypatch.setattr(graph, "log_agent_run", broken_log_agent_run)

    result = graph.run_agent("A normal request.", TEST_SESSION_ID)

    # The agent's real answer must still come through, even though
    # logging it failed entirely.
    assert result.final_response == "Here's your answer."
    assert result.error is None
