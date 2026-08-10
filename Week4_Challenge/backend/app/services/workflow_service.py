"""Workflow orchestration service — the boundary between the FastAPI layer
and the compiled LangGraph. Owns starting runs, resuming interrupted runs
(clarification / approval), and reading run snapshots for the GET
endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.types import Command

from app.config.logging_config import get_logger
from app.graph.build_graph import get_compiled_graph
from app.models.run_store import RunRecord, get_run, register_run
from app.schemas.clarification import PendingClarification
from app.state.graph_state import ResearchState, initial_state
from app.utils.errors import InvalidWorkflowStateError, RunNotFoundError
from app.utils.ids import new_run_id
from app.utils.time_utils import utc_now_iso

logger = get_logger("services.workflow")


@dataclass
class RunSnapshot:
    run_id: str
    values: dict
    is_paused: bool
    pending_interrupt: dict | None


def _thread_config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def create_run(*, user_request: str, deliverable_hint: str | None) -> RunRecord:
    """Register a new run and its initial state. Does NOT execute the graph
    — call `run_workflow` (typically via `asyncio.create_task`) to start it,
    so the API can return immediately with a run_id."""

    run_id = new_run_id()
    started_at = utc_now_iso()
    state: ResearchState = initial_state(
        run_id=run_id,
        user_request=user_request,
        deliverable_hint=deliverable_hint,
        started_at=started_at,
    )
    record = RunRecord(
        run_id=run_id,
        created_at=started_at,
        user_request=user_request,
        initial_state=state,
        status="received",
    )
    register_run(record)
    return record


def ensure_run_exists(run_id: str) -> RunRecord:
    record = get_run(run_id)
    if record is None:
        raise RunNotFoundError(f"No run found with id {run_id!r}")
    return record


def ensure_awaiting_clarification(run_id: str) -> RunRecord:
    record = ensure_run_exists(run_id)
    if record.status != "awaiting_clarification":
        raise InvalidWorkflowStateError(
            f"Run {run_id} is not awaiting clarification (current status: {record.status})"
        )
    return record


def ensure_awaiting_approval(run_id: str) -> RunRecord:
    record = ensure_run_exists(run_id)
    if record.status != "awaiting_approval":
        raise InvalidWorkflowStateError(
            f"Run {run_id} is not awaiting approval (current status: {record.status})"
        )
    return record


async def run_workflow(run_id: str) -> None:
    """Execute a freshly-created run to completion or its first interrupt."""

    record = ensure_run_exists(run_id)
    graph = get_compiled_graph()
    async with record.lock:
        try:
            result = await graph.ainvoke(record.initial_state, config=_thread_config(run_id))
        except Exception:
            record.status = "failed"
            logger.exception("workflow.run_failed", run_id=run_id)
            raise
        record.status = result.get("workflow_status", record.status)
        logger.info("workflow.run_paused_or_completed", run_id=run_id, status=record.status)


async def resume_with_clarification(run_id: str, answer: str) -> None:
    record = ensure_awaiting_clarification(run_id)
    graph = get_compiled_graph()
    async with record.lock:
        try:
            result = await graph.ainvoke(Command(resume=answer), config=_thread_config(run_id))
        except Exception:
            record.status = "failed"
            logger.exception("workflow.clarification_resume_failed", run_id=run_id)
            raise
        record.status = result.get("workflow_status", record.status)
        logger.info("workflow.clarification_resumed", run_id=run_id, status=record.status)


async def resume_with_approval(run_id: str, *, decision: str, feedback: str | None) -> None:
    record = ensure_awaiting_approval(run_id)
    graph = get_compiled_graph()
    async with record.lock:
        try:
            result = await graph.ainvoke(
                Command(resume={"decision": decision, "feedback": feedback}),
                config=_thread_config(run_id),
            )
        except Exception:
            record.status = "failed"
            logger.exception("workflow.approval_resume_failed", run_id=run_id)
            raise
        record.status = result.get("workflow_status", record.status)
        logger.info("workflow.approval_resumed", run_id=run_id, status=record.status)


def get_snapshot(run_id: str) -> RunSnapshot:
    ensure_run_exists(run_id)
    graph = get_compiled_graph()
    state_snapshot = graph.get_state(_thread_config(run_id))
    if not state_snapshot.values:
        raise RunNotFoundError(f"No run found with id {run_id!r}")

    pending_interrupt = None
    for task in state_snapshot.tasks:
        if task.interrupts:
            pending_interrupt = task.interrupts[0].value
            break

    return RunSnapshot(
        run_id=run_id,
        values=dict(state_snapshot.values),
        is_paused=bool(state_snapshot.next),
        pending_interrupt=pending_interrupt,
    )


def get_pending_clarification(snapshot: RunSnapshot) -> PendingClarification | None:
    if not snapshot.pending_interrupt or snapshot.pending_interrupt.get("type") != "clarification_required":
        return None
    return PendingClarification(
        question=snapshot.pending_interrupt["question"],
        round_number=snapshot.pending_interrupt["round"],
        missing_information=snapshot.values.get("missing_information", []),
    )


def is_awaiting_approval(snapshot: RunSnapshot) -> bool:
    return bool(snapshot.pending_interrupt) and snapshot.pending_interrupt.get("type") == "approval_required"
