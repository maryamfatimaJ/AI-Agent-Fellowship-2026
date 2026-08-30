from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_workspace
from app.api.routers.assistants import get_or_create_assistant
from app.database.deps import get_db
from app.evaluation.comparison import compare_runs
from app.evaluation.human_comparison import build_human_review_worklist, compare_human_vs_judge
from app.evaluation.runner import run_evaluation
from app.models.evaluation import EvaluationRun
from app.models.prompt_version import PromptVersion
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.evaluation import (
    ComparisonResult,
    EvaluationRunDetailRead,
    EvaluationRunListRead,
    EvaluationRunRead,
    RunEvaluationRequest,
)

router = APIRouter(prefix="/api/workspaces/{workspace_id}/evaluations", tags=["evaluations"])


@router.post("/run", response_model=EvaluationRunRead)
def run_evaluation_endpoint(
    payload: RunEvaluationRequest,
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvaluationRun:
    assistant = get_or_create_assistant(workspace, db)

    system_prompt_override = None
    if payload.prompt_version_id is not None:
        # Resolving the version id to its actual system_prompt text here (rather
        # than only tagging the run with the id) is what makes prompt-version A/B
        # comparison work through the API, not just via the CLI script — see
        # docs/evaluation/evaluation-foundation.md's prompt-versioning section.
        version = (
            db.query(PromptVersion)
            .filter(PromptVersion.id == payload.prompt_version_id, PromptVersion.workspace_id == workspace.id)
            .first()
        )
        if version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt version not found")
        system_prompt_override = version.system_prompt

    return run_evaluation(
        workspace.id,
        assistant,
        current_user.id,
        db,
        name=payload.name,
        provider=payload.provider,
        model=payload.model,
        system_prompt_override=system_prompt_override,
        prompt_version_id=payload.prompt_version_id,
        categories=payload.categories,
        limit=payload.limit,
        run_judge=payload.run_judge,
    )


@router.get("", response_model=EvaluationRunListRead)
def list_evaluation_runs(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> EvaluationRunListRead:
    query = db.query(EvaluationRun).filter(EvaluationRun.workspace_id == workspace.id)
    total = query.with_entities(func.count(EvaluationRun.id)).scalar() or 0
    rows = query.order_by(EvaluationRun.created_at.desc()).offset(offset).limit(limit).all()
    return EvaluationRunListRead(items=[EvaluationRunRead.model_validate(row) for row in rows], total=total)


def _get_owned_run(run_id: str, workspace: Workspace, db: Session) -> EvaluationRun:
    run = db.query(EvaluationRun).filter(EvaluationRun.id == run_id, EvaluationRun.workspace_id == workspace.id).first()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return run


@router.get("/compare", response_model=ComparisonResult)
def compare_evaluation_runs(
    run_a: str,
    run_b: str,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> ComparisonResult:
    _get_owned_run(run_a, workspace, db)
    _get_owned_run(run_b, workspace, db)
    return ComparisonResult(**compare_runs(run_a, run_b, db))


@router.get("/{run_id}", response_model=EvaluationRunDetailRead)
def get_evaluation_run(
    run_id: str,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> EvaluationRun:
    return _get_owned_run(run_id, workspace, db)


@router.get("/{run_id}/human-comparison")
def get_human_comparison(
    run_id: str,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _get_owned_run(run_id, workspace, db)
    return compare_human_vs_judge(run_id, db)


@router.get("/{run_id}/human-review-worklist")
def get_human_review_worklist(
    run_id: str,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> dict:
    """The 10 flagged cases with their real LLM judge scores from this run,
    paired with whatever human review has (or hasn't) happened yet — see
    app/evaluation/human_comparison.py::build_human_review_worklist()."""
    _get_owned_run(run_id, workspace, db)
    return build_human_review_worklist(run_id, db)
