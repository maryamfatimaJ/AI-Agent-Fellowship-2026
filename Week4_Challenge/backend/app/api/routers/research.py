"""POST /research — starts a new research run."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app.config.logging_config import get_logger
from app.schemas.api import ResearchRequestIn, ResearchRequestOut
from app.services import workflow_service

router = APIRouter(tags=["research"])
logger = get_logger("api.research")


@router.post("/research", response_model=ResearchRequestOut, status_code=202)
async def start_research(payload: ResearchRequestIn, background_tasks: BackgroundTasks) -> ResearchRequestOut:
    record = workflow_service.create_run(user_request=payload.text, deliverable_hint=payload.deliverable_hint)
    background_tasks.add_task(_run_in_background, record.run_id)
    return ResearchRequestOut(
        run_id=record.run_id,
        workflow_status=record.status,
        message="Research run accepted. Poll GET /workflow/{run_id} for progress.",
    )


async def _run_in_background(run_id: str) -> None:
    try:
        await workflow_service.run_workflow(run_id)
    except Exception:  # noqa: BLE001 - already logged and recorded on the run; must not crash the task loop
        logger.exception("research.background_run_failed", run_id=run_id)
