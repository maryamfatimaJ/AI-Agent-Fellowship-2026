from datetime import datetime

from pydantic import BaseModel

from app.models.trace import TraceStatus, TraceType


class TraceRead(BaseModel):
    id: str
    trace_id: str
    trace_type: TraceType
    provider: str | None
    model: str | None
    conversation_id: str | None
    message_id: str | None
    evaluation_run_id: str | None
    eval_case_id: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    input_cost_usd: float | None
    output_cost_usd: float | None
    latency_ms: float
    status: TraceStatus
    error_message: str | None
    retry_count: int
    meta: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TraceListRead(BaseModel):
    items: list[TraceRead]
    total: int
