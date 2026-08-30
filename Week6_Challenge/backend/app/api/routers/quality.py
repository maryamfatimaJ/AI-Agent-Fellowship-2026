from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_owned_workspace
from app.database.deps import get_db
from app.models.evaluation import EvaluationRun, EvaluationRunStatus
from app.models.guardrail_event import GuardrailAction, GuardrailEvent
from app.models.workspace import Workspace
from app.services.stats_service import get_performance_summary

router = APIRouter(prefix="/api/workspaces/{workspace_id}/quality", tags=["quality"])


def _latest_completed_run(workspace_id: str, db: Session) -> EvaluationRun | None:
    return (
        db.query(EvaluationRun)
        .filter(EvaluationRun.workspace_id == workspace_id, EvaluationRun.status == EvaluationRunStatus.COMPLETED)
        .order_by(EvaluationRun.created_at.desc())
        .first()
    )


@router.get("/overview")
def get_quality_overview(
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    model: str | None = Query(default=None),
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> dict:
    run = _latest_completed_run(workspace.id, db)
    performance = get_performance_summary(workspace.id, db, since=since, until=until, model=model)
    guardrail_count = (
        db.query(GuardrailEvent)
        .filter(GuardrailEvent.workspace_id == workspace.id, GuardrailEvent.triggered.is_(True))
        .count()
    )
    summary = run.summary if run else {}
    return {
        "latest_run_id": run.id if run else None,
        "task_success_rate": summary.get("overall_pass_rate"),
        "avg_judge_score": _avg_judge_score(summary),
        "n_cases": summary.get("n_cases"),
        "request_count": performance["n_requests"],
        "successful_requests": performance["successful_requests"],
        "failed_requests": performance["failed_requests"],
        "failure_rate": performance["reliability"]["error_rate"],
        "guardrail_trigger_count": guardrail_count,
        "cost_usd": performance["cost"]["total_usd"],
        "cost_per_successful_task_usd": performance["cost"]["per_successful_task_usd"],
        "latency_ms": performance["latency_ms"],
        "token_usage": performance["tokens"],
        "by_model": performance["by_model"],
        "by_prompt_version": performance["by_prompt_version"],
    }


def _avg_judge_score(summary: dict) -> float | None:
    by_category = summary.get("by_category") or {}
    scores = [c["avg_judge_score"] for c in by_category.values() if c.get("avg_judge_score") is not None]
    return round(sum(scores) / len(scores), 3) if scores else None


@router.get("/rag")
def get_quality_rag(workspace: Workspace = Depends(get_owned_workspace), db: Session = Depends(get_db)) -> dict:
    run = _latest_completed_run(workspace.id, db)
    return (run.summary.get("rag_metrics") if run and run.summary else {}) or {}


@router.get("/agent")
def get_quality_agent(workspace: Workspace = Depends(get_owned_workspace), db: Session = Depends(get_db)) -> dict:
    run = _latest_completed_run(workspace.id, db)
    return (run.summary.get("agent_metrics") if run and run.summary else {}) or {}


@router.get("/performance")
def get_quality_performance(
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    model: str | None = Query(default=None),
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> dict:
    return get_performance_summary(workspace.id, db, since=since, until=until, model=model)


@router.get("/reliability")
def get_quality_reliability(
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    model: str | None = Query(default=None),
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> dict:
    performance = get_performance_summary(workspace.id, db, since=since, until=until, model=model)
    events = db.query(GuardrailEvent).filter(GuardrailEvent.workspace_id == workspace.id).all()
    by_action: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for event in events:
        by_action[event.action.value] = by_action.get(event.action.value, 0) + 1
        by_type[event.guardrail_type] = by_type.get(event.guardrail_type, 0) + 1
    return {
        "successful_requests": performance["successful_requests"],
        "failed_requests": performance["failed_requests"],
        "retry_rate": performance["reliability"]["retry_rate"],
        "timeout_rate": performance["reliability"]["timeout_rate"],
        "error_rate": performance["reliability"]["error_rate"],
        "degraded_rate": performance["reliability"]["degraded_rate"],
        "guardrail_events_by_action": by_action,
        "guardrail_events_by_type": by_type,
        "blocked_count": by_action.get(GuardrailAction.BLOCKED.value, 0),
        "flagged_count": by_action.get(GuardrailAction.FLAGGED.value, 0),
        "sanitized_count": by_action.get(GuardrailAction.SANITIZED.value, 0),
    }
