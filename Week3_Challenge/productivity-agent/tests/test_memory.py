"""
tests/test_memory.py
-----------------------
Tests for Requirement 11 (session memory). These check that the data
needed to resolve something like "mark the second one complete"
actually reaches the decision prompt on the NEXT turn — not just that
it's sitting in a data structure somewhere.
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

SESSION_A = "session-a"
SESSION_B = "session-b"


@pytest.fixture(autouse=True)
def fresh_state():
    repository.reset_db()
    memory._session_store.clear()
    yield


def _queue_decisions_and_capture_prompts(monkeypatch, decisions):
    """Like the queue helper in other test files, but also records every prompt sent."""
    remaining = list(decisions)
    captured_prompts = []

    def fake_ask(prompt):
        captured_prompts.append(prompt)
        return remaining.pop(0)

    monkeypatch.setattr(nodes, "_ask_llm_for_decision", fake_ask)
    return captured_prompts


def test_last_shown_tasks_reach_the_next_turns_prompt(monkeypatch):
    repository.create_task(TaskCreate(title="Write proposal"))
    repository.create_task(TaskCreate(title="Fix login bug"))

    prompts = _queue_decisions_and_capture_prompts(monkeypatch, [
        # Turn 1: list tasks, then answer
        {"action": "call_tool", "tool_name": "list_tasks", "tool_arguments": {}, "reasoning_summary": "Listing."},
        {"action": "answer", "answer": "Here are your 2 tasks.", "reasoning_summary": "Reporting."},
        # Turn 2: a new decision call, whose PROMPT we'll inspect
        {"action": "answer", "answer": "The second one is 'Fix login bug'.", "reasoning_summary": "Answering."},
    ])

    graph.run_agent("Show me my tasks.", SESSION_A)
    graph.run_agent("Which one is the second one?", SESSION_A)

    # The prompt for turn 2's decision must contain the real task titles
    # from turn 1's list_tasks result, so the model CAN resolve "the second one."
    second_turn_prompt = prompts[-1]
    assert "Write proposal" in second_turn_prompt
    assert "Fix login bug" in second_turn_prompt
    assert "LAST SHOWN TASKS" in second_turn_prompt


def test_conversation_history_reaches_the_next_turns_prompt(monkeypatch):
    prompts = _queue_decisions_and_capture_prompts(monkeypatch, [
        {"action": "answer", "answer": "Critical is more urgent than High.", "reasoning_summary": "..."},
        {"action": "answer", "answer": "Sure, here's more detail.", "reasoning_summary": "..."},
    ])

    graph.run_agent("What's the difference between High and Critical?", SESSION_A)
    graph.run_agent("Can you say more about that?", SESSION_A)

    second_turn_prompt = prompts[-1]
    assert "What's the difference between High and Critical?" in second_turn_prompt
    assert "Critical is more urgent than High." in second_turn_prompt


def test_last_tool_result_reaches_the_next_turns_prompt_for_any_tool(monkeypatch):
    """
    Requirement 11 also asks the agent to remember "previous tool
    outputs" in general — last_shown_tasks (tested above) only covers
    list_tasks specifically. This checks a completely different tool
    (search_notes) is still remembered into the next turn's prompt.
    """
    from schemas import NoteCreate
    repository.create_note(NoteCreate(title="Q3 launch notes", content="Launch details"))

    prompts = _queue_decisions_and_capture_prompts(monkeypatch, [
        {"action": "call_tool", "tool_name": "search_notes", "tool_arguments": {"query": "Q3 launch"}, "reasoning_summary": "Searching."},
        {"action": "answer", "answer": "Found 1 note about the Q3 launch.", "reasoning_summary": "Reporting."},
        {"action": "answer", "answer": "Yes, that's the one about the launch.", "reasoning_summary": "Answering."},
    ])

    graph.run_agent("Search my notes for Q3 launch.", SESSION_A)
    graph.run_agent("Was that the one with the launch details?", SESSION_A)

    second_turn_prompt = prompts[-1]
    assert "MOST RECENT TOOL RESULT" in second_turn_prompt
    assert "search_notes" in second_turn_prompt


def test_user_preference_is_recorded(monkeypatch):
    _queue_decisions_and_capture_prompts(monkeypatch, [
        {
            "action": "answer",
            "answer": "Got it, I'll keep that in mind.",
            "user_preference": "Prefers to work on urgent tasks first thing in the morning.",
            "reasoning_summary": "Acknowledging a stated preference.",
        },
    ])

    graph.run_agent("Just so you know, I like to tackle urgent tasks first thing in the morning.", SESSION_A)

    session_memory = memory.get_session_memory(SESSION_A)
    assert len(session_memory.preferences) == 1
    assert "morning" in session_memory.preferences[0].lower()


def test_sessions_do_not_share_memory(monkeypatch):
    prompts = _queue_decisions_and_capture_prompts(monkeypatch, [
        {"action": "answer", "answer": "Answer for session A.", "reasoning_summary": "..."},
        {"action": "answer", "answer": "Answer for session B.", "reasoning_summary": "..."},
    ])

    graph.run_agent("Message only session A should remember", SESSION_A)
    graph.run_agent("A fresh message in a different session", SESSION_B)

    # Session B's prompt must NOT contain anything from session A's conversation.
    session_b_prompt = prompts[-1]
    assert "Message only session A should remember" not in session_b_prompt

    memory_a = memory.get_session_memory(SESSION_A)
    memory_b = memory.get_session_memory(SESSION_B)
    assert len(memory_a.messages) == 2  # user + agent
    assert len(memory_b.messages) == 2
    assert memory_a.messages[0]["content"] != memory_b.messages[0]["content"]
