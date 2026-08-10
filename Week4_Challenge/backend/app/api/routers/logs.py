"""GET /logs/{run_id} — the compiled execution trace."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import LogsOut
from app.services import workflow_service
from app.services.execution_trace_service import compile_execution_trace

router = APIRouter(tags=["logs"])


@router.get("/logs/{run_id}", response_model=LogsOut)
async def get_logs(run_id: str) -> LogsOut:
    snapshot = workflow_service.get_snapshot(run_id)
    trace = compile_execution_trace(run_id, snapshot.values)
    return LogsOut(run_id=run_id, trace=trace)
