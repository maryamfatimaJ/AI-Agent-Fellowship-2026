"""Assembles the full Evident LangGraph workflow:

User Request -> Supervisor -> Request Analysis -> Clarification (conditional)
  -> Dynamic Planning -> Parallel Research Tasks -> Evidence Store -> Analyst
  -> (optional bonus specialists, parallel) -> Critic -> Supervisor decision
  -> [revision loop back to Analyst | Writer] -> Human Approval
  -> [rejection loop back to Writer | Finalize] -> Execution Log -> END
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.edges.conditions import (
    fan_out_to_research,
    route_after_analyst,
    route_after_approval,
    route_after_request_analysis,
    route_after_supervisor_decision,
)
from app.graph.nodes.analysis_nodes import analyst_node, critic_node
from app.graph.nodes.bonus_nodes import (
    competitor_analysis_node,
    fact_checker_node,
    risk_analyst_node,
    strategy_node,
)
from app.graph.nodes.research_nodes import evidence_store_node, research_node
from app.graph.nodes.supervisor_nodes import (
    clarification_node,
    execution_log_node,
    finalize_node,
    planning_node,
    request_analysis_node,
    supervisor_decision_node,
    supervisor_intake_node,
)
from app.graph.nodes.writer_nodes import human_approval_node, writer_node
from app.memory.checkpointer import get_checkpointer
from app.state.graph_state import ResearchState


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(ResearchState)

    # --- nodes --------------------------------------------------------------
    graph.add_node("supervisor_intake_node", supervisor_intake_node)
    graph.add_node("request_analysis_node", request_analysis_node)
    graph.add_node("clarification_node", clarification_node)
    graph.add_node("planning_node", planning_node)
    graph.add_node("research_node", research_node)
    graph.add_node("evidence_store_node", evidence_store_node)
    graph.add_node("analyst_node", analyst_node)
    graph.add_node("fact_checker_node", fact_checker_node)
    graph.add_node("risk_analyst_node", risk_analyst_node)
    graph.add_node("competitor_analysis_node", competitor_analysis_node)
    graph.add_node("strategy_node", strategy_node)
    graph.add_node("critic_node", critic_node)
    graph.add_node("supervisor_decision_node", supervisor_decision_node)
    graph.add_node("writer_node", writer_node)
    graph.add_node("human_approval_node", human_approval_node)
    graph.add_node("finalize_node", finalize_node)
    graph.add_node("execution_log_node", execution_log_node)

    # --- edges ----------------------------------------------------------------
    graph.add_edge(START, "supervisor_intake_node")
    graph.add_edge("supervisor_intake_node", "request_analysis_node")

    graph.add_conditional_edges(
        "request_analysis_node",
        route_after_request_analysis,
        ["clarification_node", "planning_node"],
    )
    # Clarification pauses via interrupt(); on resume, loop back so the
    # Supervisor re-analyzes the request with the new answer incorporated.
    graph.add_edge("clarification_node", "request_analysis_node")

    # Dynamic planning fans out every independent task in parallel.
    graph.add_conditional_edges(
        "planning_node",
        fan_out_to_research,
        ["research_node", "evidence_store_node"],
    )
    # All parallel research_node instances join here automatically because
    # they share this single outgoing edge.
    graph.add_edge("research_node", "evidence_store_node")
    graph.add_edge("evidence_store_node", "analyst_node")

    # Optional bonus specialists run in parallel, then join at the Critic.
    graph.add_conditional_edges(
        "analyst_node",
        route_after_analyst,
        ["fact_checker_node", "risk_analyst_node", "competitor_analysis_node", "strategy_node", "critic_node"],
    )
    graph.add_edge("fact_checker_node", "critic_node")
    graph.add_edge("risk_analyst_node", "critic_node")
    graph.add_edge("competitor_analysis_node", "critic_node")
    graph.add_edge("strategy_node", "critic_node")

    graph.add_edge("critic_node", "supervisor_decision_node")

    # The revision loop: Supervisor sends rejected analyses back to the
    # Analyst, bounded by `settings.max_revision_cycles`.
    graph.add_conditional_edges(
        "supervisor_decision_node",
        route_after_supervisor_decision,
        ["writer_node", "analyst_node"],
    )

    graph.add_edge("writer_node", "human_approval_node")
    # Human approval pauses via interrupt(); rejection loops back to the
    # Writer (bounded by MAX_HUMAN_REVISION_ROUNDS), approval finalizes.
    graph.add_conditional_edges(
        "human_approval_node",
        route_after_approval,
        ["finalize_node", "writer_node"],
    )

    graph.add_edge("finalize_node", "execution_log_node")
    graph.add_edge("execution_log_node", END)

    return graph.compile(checkpointer=get_checkpointer())


@lru_cache(maxsize=1)
def get_compiled_graph() -> CompiledStateGraph:
    return build_graph()
