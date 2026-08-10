"""GET /report/{run_id} — the final report, if the Writer has produced one
yet (draft, pending approval, or finalized)."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import ReportOut
from app.services import workflow_service

router = APIRouter(tags=["report"])


@router.get("/report/{run_id}", response_model=ReportOut)
async def get_report(run_id: str) -> ReportOut:
    snapshot = workflow_service.get_snapshot(run_id)
    values = snapshot.values
    return ReportOut(
        run_id=run_id,
        report=values.get("final_report"),
        workflow_status=values.get("workflow_status", "unknown"),
    )
