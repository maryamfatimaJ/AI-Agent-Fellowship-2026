from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_workspace
from app.api.routers.assistants import get_or_create_assistant
from app.core.rate_limit import limiter
from app.database.deps import get_db
from app.guardrails import GuardrailBlockedError
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailRead,
    ConversationRead,
    ConversationUpdate,
    MessageRead,
    SendMessageRequest,
    SendMessageResponse,
    SetMessagePinnedRequest,
)
from app.agent.orchestrator import run_agent_turn
from app.services.chat_service import send_message

router = APIRouter(prefix="/api/workspaces/{workspace_id}/conversations", tags=["conversations"])


def _get_owned_conversation(
    conversation_id: str, workspace: Workspace, db: Session
) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.workspace_id == workspace.id)
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    assistant = get_or_create_assistant(workspace, db)
    conversation = Conversation(
        workspace_id=workspace.id,
        assistant_id=assistant.id,
        created_by=current_user.id,
        title=payload.title,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    q: str | None = None,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> list[Conversation]:
    query = db.query(Conversation).filter(Conversation.workspace_id == workspace.id)

    if q:
        pattern = f"%{q}%"
        query = (
            query.outerjoin(Message, Message.conversation_id == Conversation.id)
            .filter(or_(Conversation.title.ilike(pattern), Message.content.ilike(pattern)))
            .distinct()
        )

    return query.order_by(Conversation.updated_at.desc()).all()


@router.get("/{conversation_id}", response_model=ConversationDetailRead)
def get_conversation(
    conversation_id: str,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> Conversation:
    return _get_owned_conversation(conversation_id, workspace, db)


@router.patch("/{conversation_id}", response_model=ConversationRead)
def rename_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> Conversation:
    conversation = _get_owned_conversation(conversation_id, workspace, db)
    conversation.title = payload.title
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> None:
    conversation = _get_owned_conversation(conversation_id, workspace, db)
    db.delete(conversation)
    db.commit()


@router.post("/{conversation_id}/messages", response_model=SendMessageResponse)
@limiter.limit("30/minute")
def post_message(
    request: Request,
    conversation_id: str,
    payload: SendMessageRequest,
    background_tasks: BackgroundTasks,
    workspace: Workspace = Depends(get_owned_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SendMessageResponse:
    conversation = _get_owned_conversation(conversation_id, workspace, db)
    assistant = get_or_create_assistant(workspace, db)

    if payload.mode == "agent":
        user_message, assistant_message, outcome = run_agent_turn(
            conversation, assistant, payload.content, current_user.id, db
        )
        return SendMessageResponse(
            user_message=user_message,
            assistant_message=assistant_message,
            agent_steps=[
                {"tool_name": s.tool_name, "arguments": s.arguments, "result": s.result, "error": s.error}
                for s in outcome.steps
            ],
            pending_action_id=outcome.pending_action_id,
            hit_loop_limit=outcome.hit_loop_limit,
        )

    try:
        user_message, assistant_message = send_message(
            conversation, assistant, payload.content, current_user.id, db, background_tasks=background_tasks
        )
    except GuardrailBlockedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SendMessageResponse(user_message=user_message, assistant_message=assistant_message)


@router.patch("/{conversation_id}/messages/{message_id}", response_model=MessageRead)
def set_message_pinned(
    conversation_id: str,
    message_id: str,
    payload: SetMessagePinnedRequest,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> Message:
    conversation = _get_owned_conversation(conversation_id, workspace, db)
    message = (
        db.query(Message)
        .filter(Message.id == message_id, Message.conversation_id == conversation.id)
        .first()
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    message.pinned = payload.pinned
    db.commit()
    db.refresh(message)
    return message


@router.get("/{conversation_id}/pinned-messages", response_model=list[MessageRead])
def list_pinned_messages(
    conversation_id: str,
    workspace: Workspace = Depends(get_owned_workspace),
    db: Session = Depends(get_db),
) -> list[Message]:
    conversation = _get_owned_conversation(conversation_id, workspace, db)
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id, Message.pinned.is_(True))
        .order_by(Message.created_at)
        .all()
    )
