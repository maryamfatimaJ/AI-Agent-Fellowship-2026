from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_owned_workspace
from app.database.deps import get_db
from app.models.trace import Trace, TraceStatus, TraceType
from app.models.workspace import Workspace
from app.schemas.trace import TraceListRead, TraceRead

router = APIRouter(prefix="/api/workspaces/{workspace_id}/traces", tags=["traces"])


@router.get("", response_model=TraceListRead)
def list_traces(
    trace_type: TraceType | None = Query(default=None),
    status_filter: TraceStatus | None = Query(default=None, alias="status"),
    since: datetime | None = Query(default=None),
    evaluation_run_id: str | None = Query(default=None),
    eval_case_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> TraceListRead:
    query = db.query(Trace).filter(Trace.workspace_id == workspace.id)
    if trace_type is not None:
        query = query.filter(Trace.trace_type == trace_type)
    if status_filter is not None:
        query = query.filter(Trace.status == status_filter)
    if since is not None:
        since_aware = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        query = query.filter(Trace.created_at >= since_aware)
    if evaluation_run_id is not None:
        query = query.filter(Trace.evaluation_run_id == evaluation_run_id)
    if eval_case_id is not None:
        query = query.filter(Trace.eval_case_id == eval_case_id)

    total = query.with_entities(func.count(Trace.id)).scalar() or 0
    rows = query.order_by(Trace.created_at.desc()).offset(offset).limit(limit).all()
    return TraceListRead(items=[TraceRead.model_validate(row) for row in rows], total=total)


@router.get("/{trace_row_id}", response_model=TraceRead)
def get_trace(
    trace_row_id: str,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> TraceRead:
    trace = (
        db.query(Trace)
        .filter(Trace.id == trace_row_id, Trace.workspace_id == workspace.id)
        .first()
    )
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return TraceRead.model_validate(trace)
