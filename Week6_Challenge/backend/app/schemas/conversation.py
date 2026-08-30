from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.conversation import MessageRole


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


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
    content: str = Field(min_length=1)
    mode: str = Field(default="chat", pattern="^(chat|agent)$")


class AgentStepRead(BaseModel):
    tool_name: str
    arguments: dict
    result: dict | None = None
    error: str | None = None


class SendMessageResponse(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead
    agent_steps: list[AgentStepRead] | None = None
    pending_action_id: str | None = None
    hit_loop_limit: bool = False


class SetMessagePinnedRequest(BaseModel):
    pinned: bool
