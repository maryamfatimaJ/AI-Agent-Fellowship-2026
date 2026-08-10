from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_workspace
from app.api.routers.assistants import get_or_create_assistant
from app.database.deps import get_db
from app.models.conversation import Conversation
from app.models.skill import Skill
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.skill import SkillRead, SkillRunRequest, SkillRunResponse
from app.services.skill_service import run_skill

router = APIRouter(prefix="/api/workspaces/{workspace_id}/skills", tags=["skills"])


@router.get("", response_model=list[SkillRead])
def list_skills(workspace: Workspace = Depends(get_owned_workspace), db: Session = Depends(get_db)) -> list[Skill]:
    return (
        db.query(Skill)
        .filter(Skill.workspace_id == workspace.id, Skill.enabled.is_(True))
        .order_by(Skill.category, Skill.name)
        .all()
    )


@router.post("/{skill_id}/run", response_model=SkillRunResponse)
def run_skill_endpoint(
    skill_id: str,
    payload: SkillRunRequest,
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SkillRunResponse:
    skill = db.query(Skill).filter(Skill.id == skill_id, Skill.workspace_id == workspace.id).first()
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    conversation = None
    if payload.conversation_id:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == payload.conversation_id, Conversation.workspace_id == workspace.id)
            .first()
        )
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    assistant = get_or_create_assistant(workspace, db)
    output, user_message, assistant_message = run_skill(
        skill, payload.input, current_user.id, db, assistant=assistant, conversation=conversation
    )
    return SkillRunResponse(output=output, user_message=user_message, assistant_message=assistant_message)
