from pydantic import BaseModel, ConfigDict

from app.schemas.conversation import MessageRead


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    description: str | None
    category: str
    enabled: bool


class SkillRunRequest(BaseModel):
    input: str
    conversation_id: str | None = None


class SkillRunResponse(BaseModel):
    output: str
    user_message: MessageRead | None = None
    assistant_message: MessageRead | None = None
