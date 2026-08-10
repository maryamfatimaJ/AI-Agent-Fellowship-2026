from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.conversation import MessageRole


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationUpdate(BaseModel):
    title: str


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    assistant_id: str | None
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: MessageRole
    content: str
    citations: list[dict] | None
    pinned: bool
    created_at: datetime


class ConversationDetailRead(ConversationRead):
    messages: list[MessageRead]


class SendMessageRequest(BaseModel):
    content: str


class SendMessageResponse(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead


class SetMessagePinnedRequest(BaseModel):
    pinned: bool
