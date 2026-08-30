from datetime import datetime

from pydantic import BaseModel, Field


class PromptVersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    version_label: str = Field(min_length=1, max_length=20)
    system_prompt: str = Field(min_length=1)
    notes: str | None = None
    assistant_id: str | None = None


class PromptVersionUpdate(BaseModel):
    is_active: bool | None = None
    notes: str | None = None


class PromptVersionRead(BaseModel):
    id: str
    workspace_id: str
    assistant_id: str | None
    name: str
    version_label: str
    system_prompt: str
    notes: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
