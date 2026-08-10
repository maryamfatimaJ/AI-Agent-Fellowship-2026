from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.memory import MemoryType


class MemoryCreate(BaseModel):
    key: str
    value: str
    pinned: bool = True


class MemoryUpdate(BaseModel):
    value: str | None = None
    pinned: bool | None = None


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    key: str
    value: str
    memory_type: MemoryType
    pinned: bool
    created_at: datetime
    updated_at: datetime
