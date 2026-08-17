from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

PROMPT_CATEGORIES = ["writing", "programming", "research", "business", "education", "custom"]


class PromptTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    category: str = "custom"


class PromptTemplateUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    category: str | None = None


class PromptTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    name: str
    content: str
    category: str
    created_at: datetime
    updated_at: datetime
