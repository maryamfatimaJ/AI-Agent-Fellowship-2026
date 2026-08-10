"""Research phase graph nodes: the parallel per-task Research Agent
invocation, and the Evidence Store join point that persists the merged
evidence set before the Analyst runs."""

from __future__ import annotations

from app.agents.base import error_entry, log_entry
from app.agents.research_agent import execute_research_task
from app.config.logging_config import get_logger
from app.schemas.common import LogLevel, WorkflowStatus
from app.state.graph_state import ResearchState
from app.tools.evidence_store_tool import store_evidence
from app.utils.errors import EvidentError
from app.utils.time_utils import utc_now_iso

logger = get_logger("graph.research")


async def research_node(state: ResearchState) -> dict:
    """Executes exactly one independent research task. Invoked once per task
    via LangGraph's `Send` fan-out — many instances of this node run
    concurrently within the same superstep."""

    task = state.get("current_task")
    if task is None:
        # Defensive: should never happen since fan_out_to_research only sends
        # tasks, but a missing task must not silently corrupt the trace.
        exc = EvidentError("research_node invoked without an assigned task")
        return {"errors": [error_entry("research", exc)], "execution_log": [log_entry("research", str(exc), level=LogLevel.ERROR)]}

    logs = [log_entry("research", f"Starting task {task.task_id}: {task.description}", task_id=task.task_id)]

    try:
        outcome = await execute_research_task(task, comparison_criteria=state.get("comparison_criteria", []))
    except EvidentError as exc:
        logger.error("research.task_failed", run_id=state["run_id"], task_id=task.task_id, error=str(exc))
        logs.append(log_entry("research", f"Task {task.task_id} failed: {exc.message}", level=LogLevel.ERROR, task_id=task.task_id))
        return {
            "errors": [error_entry("research", exc, task_id=task.task_id)],
            "completed_tasks": [task.task_id],
            "execution_log": logs,
        }

    for query in outcome.queries_used:
        logs.append(log_entry("research", f"Searched: {query}", tool="search_tool", task_id=task.task_id))
    for url in outcome.sources_fetched:
        logs.append(log_entry("research", f"Extracted content from {url}", tool="content_extraction_tool", task_id=task.task_id))
    for call in outcome.llm_calls:
        logs.append(
            log_entry(
                "research",
                "LLM call completed",
                duration_ms=call.duration_ms,
                task_id=task.task_id,
                model=call.model,
                provider=call.provider,
            )
        )
    for tool_error in outcome.tool_errors:
        logs.append(log_entry("research", tool_error, level=LogLevel.WARNING, task_id=task.task_id))

    logs.append(
        log_entry(
            "research",
            f"Task {task.task_id} produced {len(outcome.evidence)} evidence item(s)",
            task_id=task.task_id,
        )
    )

    # NOTE: `updated_at` is deliberately omitted here — this node runs in
    # parallel (one instance per task), and a plain (non-Annotated) state
    # field can only accept one write per superstep. It's refreshed by the
    # sequential evidence_store_node immediately downstream instead.
    return {
        "evidence": outcome.evidence,
        "completed_tasks": [task.task_id],
        "execution_log": logs,
    }


async def evidence_store_node(state: ResearchState) -> dict:
    """Join point: all parallel research_node branches have completed by the
    time this runs (LangGraph waits for every `Send` target sharing this
    node's single upstream edge). Persists the fully-merged evidence set."""

    evidence = state.get("evidence", [])
    count = await store_evidence(state["run_id"], evidence)

    return {
        "workflow_status": WorkflowStatus.ANALYZING.value,
        "execution_log": [
            log_entry(
                "research",
                f"Persisted {count} evidence item(s) to the evidence store",
                tool="evidence_store_tool",
            )
        ],
        "updated_at": utc_now_iso(),
    }
