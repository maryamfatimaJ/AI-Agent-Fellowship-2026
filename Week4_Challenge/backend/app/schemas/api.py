"""Request/response DTOs for the FastAPI layer. Kept separate from the
internal domain schemas so the API surface can evolve independently of the
LangGraph state shape."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.clarification import PendingClarification
from app.schemas.evidence import EvidenceItem
from app.schemas.execution import ExecutionTrace
from app.schemas.report import FinalReport
from app.schemas.task import ResearchTask


class ResearchRequestIn(BaseModel):
    text: str = Field(..., min_length=3, description="The research question or objective.")
    deliverable_hint: str | None = None


class ResearchRequestOut(BaseModel):
    run_id: str
    workflow_status: str
    message: str


class ClarificationAnswerIn(BaseModel):
    run_id: str
    answer: str = Field(..., min_length=1)


class ApprovalIn(BaseModel):
    run_id: str
    feedback: str | None = None


class GenericActionOut(BaseModel):
    run_id: str
    workflow_status: str
    message: str


class WorkflowStatusOut(BaseModel):
    run_id: str
    workflow_status: str
    user_request: str
    research_objective: str | None = None
    revision_count: int = 0
    pending_clarification: PendingClarification | None = None
    awaiting_approval: bool = False
    errors: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class TaskListOut(BaseModel):
    run_id: str
    tasks: list[ResearchTask]


class EvidenceListOut(BaseModel):
    run_id: str
    evidence: list[EvidenceItem]


class LogsOut(BaseModel):
    run_id: str
    trace: ExecutionTrace


class ReportOut(BaseModel):
    run_id: str
    report: FinalReport | None
    workflow_status: str


class HealthOut(BaseModel):
    status: str
    llm_provider: str
    active_runs: int
