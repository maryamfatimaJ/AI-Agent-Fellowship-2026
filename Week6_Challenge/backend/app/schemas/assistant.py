from pydantic import BaseModel, ConfigDict, Field


class AssistantUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    system_prompt: str | None = None
    personality: str | None = None
    response_style: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)


class AssistantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    role: str | None
    system_prompt: str | None
    personality: str | None
    response_style: str
    model_provider: str
    model_name: str | None
    temperature: float
    max_tokens: int
