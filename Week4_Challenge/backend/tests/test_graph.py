"""Graph-level tests: conditional edge routing in isolation, and full
end-to-end runs through the compiled LangGraph (with every LLM call and
external tool call stubbed via `happy_path_llm` / `patch_external_tools`)."""

from __future__ import annotations

from langgraph.types import Command, Send

from app.graph.build_graph import get_compiled_graph
from app.graph.edges.conditions import (
    fan_out_to_research,
    route_after_analyst,
    route_after_approval,
    route_after_request_analysis,
    route_after_supervisor_decision,
)
from app.schemas.task import ResearchTask
from app.state.graph_state import initial_state


def _thread_config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


# --- conditional edge unit tests ---------------------------------------------


def test_route_after_request_analysis_needs_clarification():
    state = initial_state(run_id="r1", user_request="x", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")
    state["needs_clarification"] = True
    assert route_after_request_analysis(state) == "clarification_node"


def test_route_after_request_analysis_proceeds_to_planning():
    state = initial_state(run_id="r1", user_request="x", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")
    state["needs_clarification"] = False
    assert route_after_request_analysis(state) == "planning_node"


def test_fan_out_to_research_sends_one_per_task():
    state = initial_state(run_id="r1", user_request="x", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")
    state["task_plan"] = [
        ResearchTask(task_id="t1", description="d1", research_question="q1"),
        ResearchTask(task_id="t2", description="d2", research_question="q2"),
    ]
    sends = fan_out_to_research(state)
    assert all(isinstance(s, Send) for s in sends)
    assert [s.node for s in sends] == ["research_node", "research_node"]
    assert {s.arg["current_task"].task_id for s in sends} == {"t1", "t2"}


def test_fan_out_to_research_falls_back_to_evidence_store_when_plan_empty():
    state = initial_state(run_id="r1", user_request="x", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")
    state["task_plan"] = []
    sends = fan_out_to_research(state)
    assert len(sends) == 1
    assert sends[0].node == "evidence_store_node"


def test_route_after_analyst_fans_out_bonus_agents_when_enabled(monkeypatch):
    from app.graph.edges import conditions

    class _FakeSettings:
        enable_bonus_agents = True

    monkeypatch.setattr(conditions, "get_settings", lambda: _FakeSettings())
    state = initial_state(run_id="r1", user_request="x", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")
    result = route_after_analyst(state)
    assert isinstance(result, list)
    assert {s.node for s in result} == {
        "fact_checker_node",
        "risk_analyst_node",
        "competitor_analysis_node",
        "strategy_node",
    }


def test_route_after_analyst_skips_bonus_agents_when_disabled(monkeypatch):
    from app.graph.edges import conditions

    class _FakeSettings:
        enable_bonus_agents = False

    monkeypatch.setattr(conditions, "get_settings", lambda: _FakeSettings())
    state = initial_state(run_id="r1", user_request="x", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")
    assert route_after_analyst(state) == "critic_node"


def test_route_after_supervisor_decision():
    state = initial_state(run_id="r1", user_request="x", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")
    state["supervisor_decision"] = "advance_to_writer"
    assert route_after_supervisor_decision(state) == "writer_node"
    state["supervisor_decision"] = "send_back_for_revision"
    assert route_after_supervisor_decision(state) == "analyst_node"


def test_route_after_approval():
    state = initial_state(run_id="r1", user_request="x", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")
    state["approval_status"] = "approved"
    assert route_after_approval(state) == "finalize_node"

    state["approval_status"] = "rejected"
    state["human_revision_count"] = 1
    assert route_after_approval(state) == "writer_node"

    state["human_revision_count"] = 2
    assert route_after_approval(state) == "finalize_node"


# --- full end-to-end graph runs -----------------------------------------------


def test_graph_compiles_with_expected_nodes():
    graph = get_compiled_graph()
    node_names = set(graph.get_graph().nodes.keys())
    assert {
        "supervisor_intake_node",
        "request_analysis_node",
        "clarification_node",
        "planning_node",
        "research_node",
        "evidence_store_node",
        "analyst_node",
        "critic_node",
        "supervisor_decision_node",
        "writer_node",
        "human_approval_node",
        "finalize_node",
        "execution_log_node",
    }.issubset(node_names)


async def test_full_workflow_reaches_approval_then_completes(happy_path_llm):
    happy_path_llm()
    graph = get_compiled_graph()
    run_id = "run_graph_test_happy"
    state = initial_state(run_id=run_id, user_request="Should we enter the market?", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")

    result = await graph.ainvoke(state, config=_thread_config(run_id))
    assert result["workflow_status"] == "awaiting_approval"
    assert result["final_report"] is not None
    assert len(result["evidence"]) == 2
    assert set(result["completed_tasks"]) == {"t1", "t2"}
    assert len(result["bonus_insights"]) == 4

    final = await graph.ainvoke(Command(resume={"decision": "approved", "feedback": None}), config=_thread_config(run_id))
    assert final["workflow_status"] == "completed"
    assert final["final_report"].approval_status == "approved"


async def test_full_workflow_rejection_then_second_approval(happy_path_llm):
    happy_path_llm()
    graph = get_compiled_graph()
    run_id = "run_graph_test_reject"
    state = initial_state(run_id=run_id, user_request="Should we enter the market?", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")

    await graph.ainvoke(state, config=_thread_config(run_id))
    rejected = await graph.ainvoke(
        Command(resume={"decision": "rejected", "feedback": "Please tighten the recommendation."}),
        config=_thread_config(run_id),
    )
    # First rejection loops back to the Writer, which re-generates and pauses
    # again for approval (bounded by MAX_HUMAN_REVISION_ROUNDS = 1).
    assert rejected["workflow_status"] == "awaiting_approval"
    assert rejected["human_revision_count"] == 1

    final = await graph.ainvoke(Command(resume={"decision": "approved", "feedback": None}), config=_thread_config(run_id))
    assert final["workflow_status"] == "completed"


async def test_full_workflow_clarification_round_then_completes(happy_path_llm):
    from app.schemas.request import StructuredRequest

    ambiguous_then_resolved = [
        StructuredRequest(
            objective="Decide whether to enter a market",
            research_questions=[],
            deliverable="decision brief",
            is_ambiguous=True,
            clarification_question="Which market or product should this focus on?",
        ),
        StructuredRequest(
            objective="Decide whether to enter the vertical SaaS market",
            research_questions=["Is the market growing?", "Who are the competitors?"],
            deliverable="decision brief",
            comparison_criteria=["growth", "competition"],
            entities=["Product A", "Product B"],
            is_ambiguous=False,
        ),
    ]
    happy_path_llm(structured_request=ambiguous_then_resolved)

    graph = get_compiled_graph()
    run_id = "run_graph_test_clarify"
    state = initial_state(run_id=run_id, user_request="Should we enter a market?", deliverable_hint=None, started_at="2026-01-01T00:00:00+00:00")

    paused = await graph.ainvoke(state, config=_thread_config(run_id))
    assert paused["workflow_status"] == "awaiting_clarification"

    snapshot = graph.get_state(_thread_config(run_id))
    pending = snapshot.tasks[0].interrupts[0].value
    assert pending["type"] == "clarification_required"
    assert "market" in pending["question"].lower() or "product" in pending["question"].lower()

    resumed = await graph.ainvoke(Command(resume="Focus on vertical SaaS, comparing Product A and Product B."), config=_thread_config(run_id))
    assert resumed["workflow_status"] == "awaiting_approval"
    assert resumed["clarification_round"] == 1
    assert len(resumed["clarifications"]) == 1
