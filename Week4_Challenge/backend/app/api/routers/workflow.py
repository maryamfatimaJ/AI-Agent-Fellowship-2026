"""GET /workflow/{run_id} — current workflow status, including any pending
clarification question or approval checkpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import WorkflowStatusOut
from app.services import workflow_service

router = APIRouter(tags=["workflow"])


@router.get("/workflow/{run_id}", response_model=WorkflowStatusOut)
async def get_workflow_status(run_id: str) -> WorkflowStatusOut:
    snapshot = workflow_service.get_snapshot(run_id)
    values = snapshot.values

    return WorkflowStatusOut(
        run_id=run_id,
        workflow_status=values.get("workflow_status", "unknown"),
        user_request=values.get("user_request", ""),
        research_objective=values.get("research_objective") or None,
        revision_count=values.get("revision_count", 0),
        pending_clarification=workflow_service.get_pending_clarification(snapshot),
        awaiting_approval=workflow_service.is_awaiting_approval(snapshot),
        errors=[error.message for error in values.get("errors", [])],
        created_at=values.get("started_at"),
        updated_at=values.get("updated_at"),
    )
