"""Optional bonus specialist nodes (Fact Checker, Risk Analyst, Competitor
Analysis, Strategy). All four run in parallel after the Analyst, fan back
into the Critic. Each is non-critical: a failure here is logged and
skipped rather than failing the whole run — these are enhancements, not
load-bearing pipeline stages.

`updated_at` is deliberately omitted from every return here: these four
nodes run concurrently in the same superstep, and a plain (non-Annotated)
state field can only accept one write per step. It's refreshed by the
sequential critic_node immediately downstream instead.
"""

from __future__ import annotations

from app.agents.base import error_entry, log_entry
from app.agents.competitor_analysis_agent import analyze_competitors
from app.agents.fact_checker_agent import check_facts
from app.agents.risk_analyst_agent import analyze_risk
from app.agents.strategy_agent import propose_strategy
from app.config.logging_config import get_logger
from app.schemas.common import LogLevel
from app.state.graph_state import ResearchState
from app.utils.errors import EvidentError

logger = get_logger("graph.bonus")


async def fact_checker_node(state: ResearchState) -> dict:
    try:
        insight, meta = await check_facts(analysis=state["analysis"], evidence=state.get("evidence", []))
    except EvidentError as exc:
        logger.warning("fact_checker.skipped", run_id=state["run_id"], error=str(exc))
        return {"errors": [error_entry("fact_checker", exc)], "execution_log": [log_entry("fact_checker", "Skipped due to error", level=LogLevel.WARNING)]}

    return {
        "bonus_insights": [insight],
        "execution_log": [log_entry("fact_checker", "Completed fact-check pass", duration_ms=meta.duration_ms)],
    }


async def risk_analyst_node(state: ResearchState) -> dict:
    try:
        insight, meta = await analyze_risk(
            objective=state["research_objective"], analysis=state["analysis"], evidence=state.get("evidence", [])
        )
    except EvidentError as exc:
        logger.warning("risk_analyst.skipped", run_id=state["run_id"], error=str(exc))
        return {"errors": [error_entry("risk_analyst", exc)], "execution_log": [log_entry("risk_analyst", "Skipped due to error", level=LogLevel.WARNING)]}

    return {
        "bonus_insights": [insight],
        "execution_log": [log_entry("risk_analyst", "Completed risk analysis", duration_ms=meta.duration_ms)],
    }


async def competitor_analysis_node(state: ResearchState) -> dict:
    try:
        insight, meta = await analyze_competitors(
            objective=state["research_objective"],
            entities=state.get("entities", []),
            analysis=state["analysis"],
            evidence=state.get("evidence", []),
        )
    except EvidentError as exc:
        logger.warning("competitor_analysis.skipped", run_id=state["run_id"], error=str(exc))
        return {"errors": [error_entry("competitor_analysis", exc)], "execution_log": [log_entry("competitor_analysis", "Skipped due to error", level=LogLevel.WARNING)]}

    return {
        "bonus_insights": [insight],
        "execution_log": [log_entry("competitor_analysis", "Completed competitor analysis", duration_ms=meta.duration_ms)],
    }


async def strategy_node(state: ResearchState) -> dict:
    try:
        insight, meta = await propose_strategy(
            objective=state["research_objective"],
            deliverable=state.get("deliverable", ""),
            analysis=state["analysis"],
            evidence=state.get("evidence", []),
        )
    except EvidentError as exc:
        logger.warning("strategy.skipped", run_id=state["run_id"], error=str(exc))
        return {"errors": [error_entry("strategy", exc)], "execution_log": [log_entry("strategy", "Skipped due to error", level=LogLevel.WARNING)]}

    return {
        "bonus_insights": [insight],
        "execution_log": [log_entry("strategy", "Completed strategy pass", duration_ms=meta.duration_ms)],
    }
