from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_owned_workspace
from app.database.deps import get_db
from app.models.conversation import Conversation, Message
from app.models.document import Document
from app.models.memory import Memory
from app.models.prompt_template import PromptTemplate
from app.models.skill import Skill
from app.models.telemetry import Usage
from app.models.workspace import Workspace
from app.schemas.dashboard import ActivityItem, DashboardCounts, DashboardRead, DashboardUsage

router = APIRouter(prefix="/api/workspaces/{workspace_id}/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardRead)
def get_dashboard(workspace: Workspace = Depends(get_owned_workspace), db: Session = Depends(get_db)) -> DashboardRead:
    conversation_count = db.query(func.count(Conversation.id)).filter(Conversation.workspace_id == workspace.id).scalar() or 0
    message_count = (
        db.query(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.workspace_id == workspace.id)
        .scalar()
        or 0
    )
    document_count = db.query(func.count(Document.id)).filter(Document.workspace_id == workspace.id).scalar() or 0
    memory_count = db.query(func.count(Memory.id)).filter(Memory.workspace_id == workspace.id).scalar() or 0
    prompt_count = (
        db.query(func.count(PromptTemplate.id)).filter(PromptTemplate.workspace_id == workspace.id).scalar() or 0
    )
    skill_count = (
        db.query(func.count(Skill.id))
        .filter(Skill.workspace_id == workspace.id, Skill.enabled.is_(True))
        .scalar()
        or 0
    )

    usage_row = (
        db.query(func.coalesce(func.sum(Usage.input_tokens), 0), func.coalesce(func.sum(Usage.output_tokens), 0), func.coalesce(func.sum(Usage.cost_usd), 0.0))
        .filter(Usage.workspace_id == workspace.id)
        .first()
    )
    total_input, total_output, total_cost = usage_row or (0, 0, 0.0)

    activity: list[ActivityItem] = []
    for conversation in (
        db.query(Conversation)
        .filter(Conversation.workspace_id == workspace.id)
        .order_by(Conversation.updated_at.desc())
        .limit(5)
        .all()
    ):
        activity.append(
            ActivityItem(
                type="conversation",
                title=conversation.title or "New conversation",
                timestamp=conversation.updated_at,
            )
        )
    for document in (
        db.query(Document).filter(Document.workspace_id == workspace.id).order_by(Document.created_at.desc()).limit(5).all()
    ):
        activity.append(ActivityItem(type="document", title=document.filename, timestamp=document.created_at))
    for memory in (
        db.query(Memory).filter(Memory.workspace_id == workspace.id).order_by(Memory.updated_at.desc()).limit(5).all()
    ):
        activity.append(ActivityItem(type="memory", title=memory.value[:80], timestamp=memory.updated_at))

    activity.sort(key=lambda item: item.timestamp, reverse=True)

    return DashboardRead(
        counts=DashboardCounts(
            conversations=conversation_count,
            messages=message_count,
            documents=document_count,
            memory_items=memory_count,
            prompt_templates=prompt_count,
            skills=skill_count,
        ),
        usage=DashboardUsage(
            total_input_tokens=int(total_input),
            total_output_tokens=int(total_output),
            estimated_cost_usd=round(float(total_cost), 4),
        ),
        recent_activity=activity[:8],
    )
