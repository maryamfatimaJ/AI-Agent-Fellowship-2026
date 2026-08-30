from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_workspace
from app.database.deps import get_db
from app.models.guardrail_event import (
    GuardrailAction,
    GuardrailDirection,
    GuardrailEvent,
    PendingAction,
    PendingActionStatus,
)
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.guardrail import (
    GuardrailEventListRead,
    GuardrailEventRead,
    PendingActionDecisionRequest,
    PendingActionRead,
)

router = APIRouter(prefix="/api/workspaces/{workspace_id}", tags=["guardrails"])


@router.get("/guardrail-events", response_model=GuardrailEventListRead)
def list_guardrail_events(
    guardrail_type: str | None = Query(default=None),
    action: GuardrailAction | None = Query(default=None),
    direction: GuardrailDirection | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> GuardrailEventListRead:
    query = db.query(GuardrailEvent).filter(GuardrailEvent.workspace_id == workspace.id)
    if guardrail_type is not None:
        query = query.filter(GuardrailEvent.guardrail_type == guardrail_type)
    if action is not None:
        query = query.filter(GuardrailEvent.action == action)
    if direction is not None:
        query = query.filter(GuardrailEvent.direction == direction)

    total = query.with_entities(func.count(GuardrailEvent.id)).scalar() or 0
    rows = query.order_by(GuardrailEvent.created_at.desc()).offset(offset).limit(limit).all()
    return GuardrailEventListRead(items=[GuardrailEventRead.model_validate(row) for row in rows], total=total)


@router.get("/pending-actions", response_model=list[PendingActionRead])
def list_pending_actions(
    status_filter: PendingActionStatus | None = Query(default=None, alias="status"),
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> list[PendingAction]:
    query = db.query(PendingAction).filter(PendingAction.workspace_id == workspace.id)
    if status_filter is not None:
        query = query.filter(PendingAction.status == status_filter)
    return query.order_by(PendingAction.created_at.desc()).all()


@router.post("/pending-actions/{action_id}/decision", response_model=PendingActionRead)
def decide_pending_action(
    action_id: str,
    payload: PendingActionDecisionRequest,
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PendingAction:
    from app.agent.tools import execute_approved_action

    pending_action = (
        db.query(PendingAction)
        .filter(PendingAction.id == action_id, PendingAction.workspace_id == workspace.id)
        .first()
    )
    if pending_action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending action not found")
    if pending_action.status != PendingActionStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This action has already been decided")

    pending_action.decided_by = current_user.id
    if payload.approve:
        pending_action.status = PendingActionStatus.APPROVED
        pending_action.result = execute_approved_action(pending_action, db)
    else:
        pending_action.status = PendingActionStatus.REJECTED
        pending_action.result = {"skipped": True}

    db.commit()
    db.refresh(pending_action)
    return pending_action
