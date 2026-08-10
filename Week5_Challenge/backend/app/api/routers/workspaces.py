from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_workspace
from app.database.deps import get_db
from app.models.assistant import Assistant
from app.models.prompt_template import PromptTemplate
from app.models.settings import WorkspaceSettings
from app.models.skill import Skill
from app.models.user import User
from app.models.workspace import Workspace
from app.prompts.defaults import DEFAULT_PROMPTS
from app.schemas.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from app.skills.defaults import DEFAULT_SKILLS

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    workspace = Workspace(owner_id=current_user.id, name=payload.name, description=payload.description)
    db.add(workspace)
    db.flush()

    db.add(Assistant(workspace_id=workspace.id, name="Assistant"))
    db.add(WorkspaceSettings(workspace_id=workspace.id, data={}))

    for skill in DEFAULT_SKILLS:
        db.add(
            Skill(
                workspace_id=workspace.id,
                name=skill["name"],
                description=skill["description"],
                category=skill["category"],
                config={"prompt_template": skill["prompt_template"]},
            )
        )
    for prompt in DEFAULT_PROMPTS:
        db.add(
            PromptTemplate(
                workspace_id=workspace.id,
                created_by=current_user.id,
                name=prompt["name"],
                category=prompt["category"],
                content=prompt["content"],
            )
        )

    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Workspace]:
    return db.query(Workspace).filter(Workspace.owner_id == current_user.id).all()


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(workspace: Workspace = Depends(get_owned_workspace)) -> Workspace:
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
def update_workspace(
    payload: WorkspaceUpdate,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> Workspace:
    if payload.name is not None:
        workspace.name = payload.name
    if payload.description is not None:
        workspace.description = payload.description
    db.commit()
    db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace: Workspace = Depends(get_owned_workspace), db: Session = Depends(get_db)) -> None:
    db.delete(workspace)
    db.commit()
