"""POST /approve and POST /reject — the human-in-the-loop checkpoint gating
the final report."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app.config.logging_config import get_logger
from app.schemas.api import ApprovalIn, GenericActionOut
from app.services import workflow_service

router = APIRouter(tags=["approval"])
logger = get_logger("api.approval")


@router.post("/approve", response_model=GenericActionOut, status_code=202)
async def approve_report(payload: ApprovalIn, background_tasks: BackgroundTasks) -> GenericActionOut:
    record = workflow_service.ensure_awaiting_approval(payload.run_id)
    background_tasks.add_task(_resume_in_background, payload.run_id, "approved", payload.feedback)
    return GenericActionOut(
        run_id=payload.run_id,
        workflow_status=record.status,
        message="Approval received. Finalizing report.",
    )


@router.post("/reject", response_model=GenericActionOut, status_code=202)
async def reject_report(payload: ApprovalIn, background_tasks: BackgroundTasks) -> GenericActionOut:
    record = workflow_service.ensure_awaiting_approval(payload.run_id)
    background_tasks.add_task(_resume_in_background, payload.run_id, "rejected", payload.feedback)
    return GenericActionOut(
        run_id=payload.run_id,
        workflow_status=record.status,
        message="Rejection received. Sending back to the Writer agent (bounded retry).",
    )


async def _resume_in_background(run_id: str, decision: str, feedback: str | None) -> None:
    try:
        await workflow_service.resume_with_approval(run_id, decision=decision, feedback=feedback)
    except Exception:  # noqa: BLE001 - already logged and recorded on the run
        logger.exception("approval.background_resume_failed", run_id=run_id, decision=decision)
