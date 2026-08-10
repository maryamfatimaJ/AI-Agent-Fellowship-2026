"""Conditional edge functions — the routing logic that turns the linear
pipeline diagram into an actual graph with branches, fan-out, and loops.

Every function here is a pure function of `ResearchState`, making the
routing logic independently unit-testable without running the graph or
calling an LLM.
"""

from __future__ import annotations

from langgraph.types import Send

from app.config.settings import get_settings
from app.graph.nodes.writer_nodes import MAX_HUMAN_REVISION_ROUNDS
from app.state.graph_state import ResearchState

# --- after request analysis -------------------------------------------------


def route_after_request_analysis(state: ResearchState) -> str:
    if state.get("needs_clarification"):
        return "clarification_node"
    return "planning_node"


# --- after planning: fan out independent research tasks in parallel --------


def fan_out_to_research(state: ResearchState) -> list[Send]:
    tasks = state.get("task_plan", [])
    if not tasks:
        # Planning produced nothing usable — this is a recoverable failure
        # surfaced via `errors`; routing to evidence_store_node with zero
        # evidence lets the pipeline still terminate cleanly rather than
        # deadlocking on an empty fan-out.
        return [Send("evidence_store_node", {**state})]

    return [Send("research_node", {**state, "current_task": task}) for task in tasks]


# --- after analyst: optionally fan out bonus specialists -------------------


def route_after_analyst(state: ResearchState) -> list[Send] | str:
    settings = get_settings()
    if not settings.enable_bonus_agents:
        return "critic_node"

    return [
        Send("fact_checker_node", {**state}),
        Send("risk_analyst_node", {**state}),
        Send("competitor_analysis_node", {**state}),
        Send("strategy_node", {**state}),
    ]


# --- after the Supervisor's post-critic decision: the revision loop -------


def route_after_supervisor_decision(state: ResearchState) -> str:
    if state.get("supervisor_decision") == "advance_to_writer":
        return "writer_node"
    return "analyst_node"


# --- after human approval --------------------------------------------------


def route_after_approval(state: ResearchState) -> str:
    if state.get("approval_status") == "approved":
        return "finalize_node"
    if state.get("human_revision_count", 0) > MAX_HUMAN_REVISION_ROUNDS:
        return "finalize_node"
    return "writer_node"


__all__ = [
    "route_after_request_analysis",
    "fan_out_to_research",
    "route_after_analyst",
    "route_after_supervisor_decision",
    "route_after_approval",
]
