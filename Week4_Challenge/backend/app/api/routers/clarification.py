"""POST /clarification — answers a pending clarification question and
resumes a paused workflow."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app.config.logging_config import get_logger
from app.schemas.api import ClarificationAnswerIn, GenericActionOut
from app.services import workflow_service

router = APIRouter(tags=["clarification"])
logger = get_logger("api.clarification")


@router.post("/clarification", response_model=GenericActionOut, status_code=202)
async def submit_clarification(payload: ClarificationAnswerIn, background_tasks: BackgroundTasks) -> GenericActionOut:
    record = workflow_service.ensure_awaiting_clarification(payload.run_id)
    background_tasks.add_task(_resume_in_background, payload.run_id, payload.answer)
    return GenericActionOut(
        run_id=payload.run_id,
        workflow_status=record.status,
        message="Clarification received. Resuming workflow.",
    )


async def _resume_in_background(run_id: str, answer: str) -> None:
    try:
        await workflow_service.resume_with_clarification(run_id, answer)
    except Exception:  # noqa: BLE001 - already logged and recorded on the run
        logger.exception("clarification.background_resume_failed", run_id=run_id)
