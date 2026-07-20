"""
tests/test_agent.py
----------------------
Tests for agent/graph.py. The LLM decision call is mocked with a queue
of canned responses — the agent controller's CONTROL FLOW is what's
under test here (when it stops, when it calls a tool, when it respects
limits), not Gemini's actual judgment, which can't be tested
deterministically anyway.
"""

import os
import tempfile

import pytest

_temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = "sqlite:///" + _temp_db_file.name
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("SECRET_KEY", "test-secret-not-real")

from database import repository
from database.models import Priority
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
        if not remaining:
            raise AssertionError("The agent asked for a decision more times than this test expected.")
        return remaining.pop(0)

    monkeypatch.setattr(nodes, "_ask_llm_for_decision", fake_ask)


def test_direct_answer_does_not_call_a_tool(monkeypatch):
    _queue_decisions(monkeypatch, [
        {
            "action": "answer",
            "answer": "High priority is urgent; Critical priority means it needs attention immediately.",
            "reasoning_summary": "Answering a conceptual question directly.",
        },
    ])

    result = graph.run_agent("Explain the difference between high and critical priority.", TEST_SESSION_ID)

    assert result.final_response is not None
    assert result.error is None
    assert result.pending_approval is None
    assert not any(step.stage == "executing" for step in result.steps)


def test_tool_call_applies_filters_and_returns_results(monkeypatch):
    repository.create_task(TaskCreate(title="Fix critical bug", priority=Priority.CRITICAL))
    repository.create_task(TaskCreate(title="Low priority cleanup", priority=Priority.LOW))

    _queue_decisions(monkeypatch, [
        {
            "action": "call_tool",
            "tool_name": "list_tasks",
            "tool_arguments": {"priority": "Critical"},
            "reasoning_summary": "Listing critical-priority tasks.",
        },
        {
            "action": "answer",
            "answer": "You have 1 critical task: Fix critical bug.",
            "reasoning_summary": "Reporting the result.",
        },
    ])

    result = graph.run_agent("Show me critical tasks due this week.", TEST_SESSION_ID)

    assert result.final_response == "You have 1 critical task: Fix critical bug."
    executed_steps = [step for step in result.steps if step.stage == "executing"]
    assert len(executed_steps) == 1
    assert executed_steps[0].tool_name == "list_tasks"


def test_approval_required_tool_stops_before_executing(monkeypatch):
    task = repository.create_task(TaskCreate(title="Finish the report"))

    _queue_decisions(monkeypatch, [
        {
            "action": "call_tool",
            "tool_name": "complete_task",
            "tool_arguments": {"task_id": task.task_id},
            "reasoning_summary": "Marking the task complete.",
        },
    ])

    result = graph.run_agent("Mark the report task as complete.", TEST_SESSION_ID)

    assert result.pending_approval is not None
    assert result.pending_approval.tool_name == "complete_task"
    assert result.final_response is None

    unchanged = repository.get_task(task.task_id)
    assert unchanged.status.value == "Pending"


def test_resuming_after_approval_executes_the_tool(monkeypatch):
    task = repository.create_task(TaskCreate(title="Finish the report"))

    _queue_decisions(monkeypatch, [
        {
            "action": "answer",
            "answer": "Done - the task is marked complete.",
            "reasoning_summary": "Confirming completion.",
        },
    ])

    result = graph.run_agent(
        "Mark the report task as complete.",
        TEST_SESSION_ID,
        already_approved={"tool_name": "complete_task", "tool_arguments": {"task_id": task.task_id}},
    )

    assert result.final_response == "Done - the task is marked complete."
    now_completed = repository.get_task(task.task_id)
    assert now_completed.status.value == "Completed"


def test_duplicate_tool_call_is_stopped(monkeypatch):
    same_decision = {
        "action": "call_tool",
        "tool_name": "list_tasks",
        "tool_arguments": {},
        "reasoning_summary": "Listing tasks.",
    }
    _queue_decisions(monkeypatch, [same_decision] * 8)

    result = graph.run_agent("List my tasks over and over.", TEST_SESSION_ID)

    assert result.error is not None
    assert "repeating" in result.error.lower()


def test_max_agent_steps_is_enforced(monkeypatch):
    decisions = []
    for i in range(20):
        decisions.append({
            "action": "call_tool",
            "tool_name": "list_tasks",
            "tool_arguments": {"tag": str(i)},
            "reasoning_summary": "Looping.",
        })
    _queue_decisions(monkeypatch, decisions)

    result = graph.run_agent("Do something that keeps needing another tool call.", TEST_SESSION_ID)

    assert result.error is not None
    assert "maximum" in result.error.lower()


def test_unknown_tool_name_is_reported_clearly(monkeypatch):
    _queue_decisions(monkeypatch, [
        {
            "action": "call_tool",
            "tool_name": "delete_everything",
            "tool_arguments": {},
            "reasoning_summary": "Trying an unsupported tool.",
        },
    ])

    result = graph.run_agent("Do something unsupported.", TEST_SESSION_ID)

    assert result.error is not None
    assert "unsupported tool" in result.error.lower()


def test_second_create_task_call_forces_approval(monkeypatch):
    """
    Requirement 7: creating multiple tasks needs approval. A single
    create_task call doesn't, but calling it a SECOND time in the same
    run must be forced into the approval gate, even though the
    registry marks create_task itself as not requiring approval.
    """
    _queue_decisions(monkeypatch, [
        {"action": "call_tool", "tool_name": "create_task", "tool_arguments": {"title": "First task"}, "reasoning_summary": "Creating first task."},
        {"action": "call_tool", "tool_name": "create_task", "tool_arguments": {"title": "Second task"}, "reasoning_summary": "Creating second task."},
    ])

    result = graph.run_agent("Create two tasks: First task and Second task.", TEST_SESSION_ID)

    # The first create_task should have executed already (no approval needed).
    executed_first = any(
        step.stage == "executing" and step.tool_arguments and step.tool_arguments.get("title") == "First task"
        for step in result.steps
    )
    assert executed_first

    # The second one should be blocked, waiting for approval instead of executing.
    assert result.pending_approval is not None
    assert result.pending_approval.tool_name == "create_task"
    assert result.pending_approval.tool_arguments["title"] == "Second task"
