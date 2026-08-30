from datetime import datetime

from pydantic import BaseModel

from app.models.guardrail_event import GuardrailAction, GuardrailDirection, PendingActionStatus


class GuardrailEventRead(BaseModel):
    id: str
    conversation_id: str | None
    message_id: str | None
    direction: GuardrailDirection
    guardrail_type: str
    triggered: bool
    action: GuardrailAction
    detail: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GuardrailEventListRead(BaseModel):
    items: list[GuardrailEventRead]
    total: int


class PendingActionRead(BaseModel):
    id: str
    conversation_id: str | None
    tool_name: str
    tool_args: dict | None
    risk_level: str
    status: PendingActionStatus
    result: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PendingActionDecisionRequest(BaseModel):
    approve: bool
