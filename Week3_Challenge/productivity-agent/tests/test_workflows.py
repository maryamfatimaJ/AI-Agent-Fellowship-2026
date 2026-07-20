"""
tests/test_workflows.py
--------------------------
Requirement 6 requires at least three workflows involving multiple
tools. These tests drive the REAL agent loop (agent/graph.py) through
each one, with the LLM decision calls mocked — proving the control
flow genuinely supports chaining tool calls, gating on approval, and
producing a final answer, for all three named workflows.
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
from schemas import TaskCreate
from agent import nodes, graph, memory

SESSION_ID = "workflow-test-session"


@pytest.fixture(autouse=True)
def fresh_state():
    repository.reset_db()
    memory._session_store.clear()
    yield


def _queue_decisions(monkeypatch, decisions):
    remaining = list(decisions)

    def fake_ask(prompt):
        return remaining.pop(0)

    monkeypatch.setattr(nodes, "_ask_llm_for_decision", fake_ask)


# ============================================================
# WORKFLOW A: MEETING NOTES -> TASKS
# ============================================================

def test_workflow_a_meeting_notes_to_tasks(monkeypatch):
    fake_extraction = {
        "summary": "Team agreed on the Q3 launch plan.",
        "decisions": ["Launch date set to August 15"],
        "action_items": [
            {"description": "Update the launch timeline doc", "owner": "Sara", "deadline": "Friday"},
            {"description": "Draft the press release", "owner": "Jon", "deadline": None},
        ],
        "unresolved_questions": [],
    }
    monkeypatch.setattr("tools.planning_tools.generate_json", lambda prompt: fake_extraction)

    _queue_decisions(monkeypatch, [
        # Step 1: extract action items from the submitted notes
        {
            "action": "call_tool", "tool_name": "extract_meeting_actions",
            "tool_arguments": {"transcript": "Meeting transcript text..."},
            "reasoning_summary": "Extracting action items from the meeting notes.",
        },
        # Step 2: propose creating tasks from those action items (requires approval)
        {
            "action": "call_tool", "tool_name": "create_tasks_bulk",
            "tool_arguments": {"tasks": [
                {"title": "Update the launch timeline doc", "description": "Owner: Sara, due Friday"},
                {"title": "Draft the press release", "description": "Owner: Jon"},
            ]},
            "reasoning_summary": "Proposing tasks from the extracted action items.",
        },
    ])

    # --- Step 1 & 2: agent extracts, then proposes tasks and pauses for approval ---
    result = graph.run_agent("Create tasks from these meeting notes: ...", SESSION_ID)

    assert result.pending_approval is not None
    assert result.pending_approval.tool_name == "create_tasks_bulk"

    # --- User approves; agent creates the tasks and returns their IDs ---
    _queue_decisions(monkeypatch, [
        {"action": "answer", "answer": "Created 2 tasks.", "reasoning_summary": "Reporting the created task IDs."},
    ])

    final = graph.run_agent(
        "Create tasks from these meeting notes: ...",
        SESSION_ID,
        already_approved={"tool_name": "create_tasks_bulk", "tool_arguments": result.pending_approval.tool_arguments},
    )

    assert final.final_response == "Created 2 tasks."
    all_tasks = repository.list_tasks()
    assert len(all_tasks) == 2
    assert any(task.title == "Update the launch timeline doc" for task in all_tasks)
    assert any(task.title == "Draft the press release" for task in all_tasks)


# ============================================================
# WORKFLOW B: DAILY PLANNING
# ============================================================

def test_workflow_b_daily_planning(monkeypatch):
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    repository.create_task(TaskCreate(title="Overdue thing", priority=Priority.HIGH, due_date=yesterday))
    repository.create_task(TaskCreate(title="Routine thing", priority=Priority.LOW))

    _queue_decisions(monkeypatch, [
        # Step 1: retrieve pending tasks
        {
            "action": "call_tool", "tool_name": "list_tasks", "tool_arguments": {"status": "Pending"},
            "reasoning_summary": "Retrieving pending tasks.",
        },
        # Step 2: detect urgent/overdue tasks
        {
            "action": "call_tool", "tool_name": "detect_overdue_tasks", "tool_arguments": {},
            "reasoning_summary": "Checking for overdue tasks.",
        },
        # Step 3: generate the schedule
        {
            "action": "call_tool", "tool_name": "generate_work_plan",
            "tool_arguments": {"available_hours": 8, "date": "2026-07-20"},
            "reasoning_summary": "Building today's schedule.",
        },
        # Step 4: explain the prioritization
        {
            "action": "answer",
            "answer": "Your overdue task is scheduled first, followed by routine work.",
            "reasoning_summary": "Explaining the prioritization.",
        },
    ])

    result = graph.run_agent("Give me a work plan for today, I have 8 hours.", SESSION_ID)

    assert result.final_response == "Your overdue task is scheduled first, followed by routine work."
    executed_tools = [step.tool_name for step in result.steps if step.stage == "executing"]
    assert executed_tools == ["list_tasks", "detect_overdue_tasks", "generate_work_plan"]


# ============================================================
# WORKFLOW C: WEEKLY REVIEW
# ============================================================

def test_workflow_c_weekly_review(monkeypatch):
    completed = repository.create_task(TaskCreate(title="Shipped feature"))
    repository.complete_task(completed.task_id)

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    repository.create_task(TaskCreate(title="Overdue review", due_date=yesterday))

    blocked_task = repository.create_task(TaskCreate(title="Waiting on design"))
    from schemas import TaskUpdate
    repository.update_task(blocked_task.task_id, TaskUpdate(task_id=blocked_task.task_id, status=Status.BLOCKED))

    _queue_decisions(monkeypatch, [
        # Step 1: gather this period's tasks
        {
            "action": "call_tool", "tool_name": "list_tasks", "tool_arguments": {},
            "reasoning_summary": "Gathering this week's tasks.",
        },
        # Step 2: check what's overdue
        {
            "action": "call_tool", "tool_name": "detect_overdue_tasks", "tool_arguments": {},
            "reasoning_summary": "Checking overdue items for the report.",
        },
        # Step 3: produce the report and next week's recommendation
        {
            "action": "answer",
            "answer": "This week: 1 completed, 1 overdue, 1 blocked. Recommend tackling the overdue review first next week.",
            "reasoning_summary": "Generating the weekly report.",
        },
    ])

    result = graph.run_agent("Give me my weekly review.", SESSION_ID)

    assert "completed" in result.final_response.lower()
    assert "overdue" in result.final_response.lower()
    executed_tools = [step.tool_name for step in result.steps if step.stage == "executing"]
    assert executed_tools == ["list_tasks", "detect_overdue_tasks"]