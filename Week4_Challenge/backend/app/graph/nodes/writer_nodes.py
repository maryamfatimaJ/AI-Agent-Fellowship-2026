"""Report Writer node and the Human Approval interrupt checkpoint."""

from __future__ import annotations

from langgraph.types import interrupt

from app.agents.base import error_entry, log_entry
from app.agents.writer_agent import write_report
from app.config.logging_config import get_logger
from app.schemas.common import ApprovalDecision, LogLevel, WorkflowStatus
from app.state.graph_state import ResearchState
from app.tools.markdown_export_tool import export_markdown
from app.utils.errors import EvidentError
from app.utils.time_utils import utc_now_iso

logger = get_logger("graph.writer")

# A human reviewer gets at most one rewrite after a rejection before the run
# is finalized as rejected — bounded so the human-in-the-loop checkpoint
# cannot loop indefinitely, mirroring the Critic's revision cap.
MAX_HUMAN_REVISION_ROUNDS = 1


async def writer_node(state: ResearchState) -> dict:
    """Report Writer Agent: compile the approved analysis + evidence into a
    final markdown report. If re-entered after a human rejection, addresses
    the reviewer's feedback."""

    critic_feedback = state["critic_feedback"][-1]
    human_feedback = state.get("approval_feedback") if state.get("approval_status") == "rejected" else None

    try:
        report, meta = await write_report(
            objective=state["research_objective"],
            deliverable=state.get("deliverable", ""),
            analysis=state["analysis"],
            critic_feedback=critic_feedback,
            evidence=state.get("evidence", []),
            bonus_insights=state.get("bonus_insights", []),
            human_feedback=human_feedback,
        )
    except EvidentError as exc:
        logger.error("writer.failed", run_id=state["run_id"], error=str(exc))
        return {
            "errors": [error_entry("writer", exc, recoverable=False)],
            "workflow_status": WorkflowStatus.FAILED.value,
            "execution_log": [log_entry("writer", "Report writing failed", level=LogLevel.ERROR)],
            "updated_at": utc_now_iso(),
        }

    exported_path = await export_markdown(state["run_id"], report.markdown)

    return {
        "final_report": report,
        "approval_status": None,
        "workflow_status": WorkflowStatus.AWAITING_APPROVAL.value,
        "execution_log": [
            log_entry(
                "writer",
                "Draft report generated" + (" (revised per human feedback)" if human_feedback else ""),
                duration_ms=meta.duration_ms,
                tool="markdown_export_tool",
                path=str(exported_path),
            )
        ],
        "updated_at": utc_now_iso(),
    }


async def human_approval_node(state: ResearchState) -> dict:
    """Pause for human review of the draft report via `interrupt()`.

    Resumed via `POST /approve` or `POST /reject`, which call the graph with
    `Command(resume={"decision": "approved"|"rejected", "feedback": ...})`.
    """

    report = state.get("final_report")
    payload = interrupt(
        {
            "type": "approval_required",
            "report_title": report.title if report else None,
            "executive_summary": report.executive_summary if report else None,
        }
    )

    decision = payload.get("decision") if isinstance(payload, dict) else None
    feedback = payload.get("feedback") if isinstance(payload, dict) else None
    human_revision_count = state.get("human_revision_count", 0)

    if decision == ApprovalDecision.APPROVED.value:
        return {
            "approval_status": "approved",
            "approval_feedback": feedback,
            "workflow_status": WorkflowStatus.FINALIZING.value,
            "execution_log": [log_entry("human", "Report approved by human reviewer")],
            "updated_at": utc_now_iso(),
        }

    next_count = human_revision_count + 1
    exhausted = next_count > MAX_HUMAN_REVISION_ROUNDS
    return {
        "approval_status": "rejected",
        "approval_feedback": feedback,
        "human_revision_count": next_count,
        "workflow_status": (WorkflowStatus.REJECTED if exhausted else WorkflowStatus.REVISING).value,
        "execution_log": [
            log_entry(
                "human",
                "Report rejected"
                + (f": {feedback}" if feedback else " (no feedback given)")
                + (" — revision limit reached, finalizing as rejected" if exhausted else " — sending back to Writer"),
            )
        ],
        "updated_at": utc_now_iso(),
    }
