"""Analyst and Critic graph nodes — the core revision-loop pair."""

from __future__ import annotations

from app.agents.analyst_agent import analyze_evidence
from app.agents.base import error_entry, log_entry
from app.agents.critic_agent import critique_analysis
from app.config.logging_config import get_logger
from app.schemas.common import LogLevel, WorkflowStatus
from app.schemas.handoff import AnalystToCriticHandoff, ResearchToAnalystHandoff
from app.state.graph_state import ResearchState
from app.utils.errors import EvidentError
from app.utils.ids import new_handoff_id
from app.utils.time_utils import utc_now_iso

logger = get_logger("graph.analysis")


async def analyst_node(state: ResearchState) -> dict:
    """Analyst Agent: synthesize evidence into insights and comparisons,
    working only from `state["evidence"]`. On a revision loop, incorporates
    the most recent Critic feedback."""

    prior_feedback = state["critic_feedback"][-1] if state.get("critic_feedback") else None

    try:
        result, meta = await analyze_evidence(
            objective=state["research_objective"],
            research_questions=state.get("research_questions", []),
            comparison_criteria=state.get("comparison_criteria", []),
            evidence=state.get("evidence", []),
            prior_feedback=prior_feedback,
        )
    except EvidentError as exc:
        logger.error("analyst.failed", run_id=state["run_id"], error=str(exc))
        return {
            "errors": [error_entry("analyst", exc, recoverable=False)],
            "workflow_status": WorkflowStatus.FAILED.value,
            "execution_log": [log_entry("analyst", "Analysis failed", level=LogLevel.ERROR)],
            "updated_at": utc_now_iso(),
        }

    research_handoff = ResearchToAnalystHandoff(
        handoff_id=new_handoff_id(),
        evidence_ids=[item.evidence_id for item in state.get("evidence", [])],
        research_questions_covered=state.get("research_questions", []),
        research_questions_unanswered=result.unsupported_gaps,
    )
    analyst_handoff = AnalystToCriticHandoff(
        handoff_id=new_handoff_id(),
        analysis=result,
        revision_round=state.get("revision_count", 0),
    )

    return {
        "analysis": result,
        "workflow_status": WorkflowStatus.ANALYZING.value,
        "execution_log": [log_entry("analyst", "Completed analysis", duration_ms=meta.duration_ms)],
        "handoffs": [research_handoff.model_dump_json(), analyst_handoff.model_dump_json()],
        "updated_at": utc_now_iso(),
    }


async def critic_node(state: ResearchState) -> dict:
    """Critic Agent: evaluate (never rewrite) the Analyst's output."""

    try:
        feedback, meta = await critique_analysis(
            objective=state["research_objective"],
            comparison_criteria=state.get("comparison_criteria", []),
            evidence=state.get("evidence", []),
            analysis=state["analysis"],
            revision_round=state.get("revision_count", 0),
        )
    except EvidentError as exc:
        logger.error("critic.failed", run_id=state["run_id"], error=str(exc))
        return {
            "errors": [error_entry("critic", exc, recoverable=False)],
            "workflow_status": WorkflowStatus.FAILED.value,
            "execution_log": [log_entry("critic", "Critique failed", level=LogLevel.ERROR)],
            "updated_at": utc_now_iso(),
        }

    return {
        "critic_feedback": [feedback],
        "workflow_status": WorkflowStatus.CRITIQUING.value,
        "execution_log": [
            log_entry("critic", f"Verdict: {feedback.verdict.value}", duration_ms=meta.duration_ms)
        ],
        "updated_at": utc_now_iso(),
    }
