"""LangGraph state shape and reducer tests."""

from __future__ import annotations

from app.state.graph_state import initial_state
from app.state.reducers import merge_unique_str


def test_initial_state_has_expected_defaults():
    state = initial_state(
        run_id="run_test",
        user_request="Should we do X?",
        deliverable_hint=None,
        started_at="2026-01-01T00:00:00+00:00",
    )

    assert state["run_id"] == "run_test"
    assert state["workflow_status"] == "received"
    assert state["evidence"] == []
    assert state["task_plan"] == []
    assert state["revision_count"] == 0
    assert state["human_revision_count"] == 0
    assert state["clarification_round"] == 0
    assert state["final_report"] is None
    assert state["current_task"] is None


def test_merge_unique_str_deduplicates_across_calls():
    result = merge_unique_str(["t1"], ["t2", "t1"])
    assert result == ["t1", "t2"]


def test_merge_unique_str_handles_none_inputs():
    assert merge_unique_str(None, ["t1"]) == ["t1"]
    assert merge_unique_str(["t1"], None) == ["t1"]
    assert merge_unique_str(None, None) == []
