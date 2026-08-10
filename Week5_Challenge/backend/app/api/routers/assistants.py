from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_owned_workspace
from app.database.deps import get_db
from app.models.assistant import Assistant
from app.models.workspace import Workspace
from app.schemas.assistant import AssistantRead, AssistantUpdate

router = APIRouter(prefix="/api/workspaces/{workspace_id}/assistant", tags=["assistant"])


def get_or_create_assistant(workspace: Workspace, db: Session) -> Assistant:
    assistant = db.query(Assistant).filter(Assistant.workspace_id == workspace.id).first()
    if assistant is None:
        assistant = Assistant(workspace_id=workspace.id, name="Assistant")
        db.add(assistant)
        db.commit()
        db.refresh(assistant)
    return assistant


@router.get("", response_model=AssistantRead)
def get_assistant(workspace: Workspace = Depends(get_owned_workspace), db: Session = Depends(get_db)) -> Assistant:
    return get_or_create_assistant(workspace, db)


@router.patch("", response_model=AssistantRead)
def update_assistant(
    payload: AssistantUpdate,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> Assistant:
    assistant = get_or_create_assistant(workspace, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(assistant, field, value)
    db.commit()
    db.refresh(assistant)
    return assistant
