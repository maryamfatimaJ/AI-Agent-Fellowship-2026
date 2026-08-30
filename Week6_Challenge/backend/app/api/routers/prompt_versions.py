from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_owned_workspace
from app.database.deps import get_db
from app.models.prompt_version import PromptVersion
from app.models.workspace import Workspace
from app.schemas.prompt_version import PromptVersionCreate, PromptVersionRead, PromptVersionUpdate

router = APIRouter(prefix="/api/workspaces/{workspace_id}/prompt-versions", tags=["prompt-versions"])


@router.get("", response_model=list[PromptVersionRead])
def list_prompt_versions(
    workspace: Workspace = Depends(get_owned_workspace), db: Session = Depends(get_db)
) -> list[PromptVersion]:
    return (
        db.query(PromptVersion)
        .filter(PromptVersion.workspace_id == workspace.id)
        .order_by(PromptVersion.version_label)
        .all()
    )


@router.post("", response_model=PromptVersionRead, status_code=status.HTTP_201_CREATED)
def create_prompt_version(
    payload: PromptVersionCreate,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> PromptVersion:
    version = PromptVersion(workspace_id=workspace.id, **payload.model_dump())
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.patch("/{version_id}", response_model=PromptVersionRead)
def update_prompt_version(
    version_id: str,
    payload: PromptVersionUpdate,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> PromptVersion:
    version = (
        db.query(PromptVersion)
        .filter(PromptVersion.id == version_id, PromptVersion.workspace_id == workspace.id)
        .first()
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt version not found")

    updates = payload.model_dump(exclude_unset=True)
    if updates.get("is_active"):
        # only one active version per workspace at a time
        db.query(PromptVersion).filter(PromptVersion.workspace_id == workspace.id).update({"is_active": False})
    for field, value in updates.items():
        setattr(version, field, value)
    db.commit()
    db.refresh(version)
    return version
