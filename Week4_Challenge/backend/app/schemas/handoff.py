"""Structured handoff envelopes. Every inter-agent transition in the graph
passes one of these — never a raw dict or free-form string — so the
execution trace can record exactly what was handed off and why.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.analysis import AnalysisResult
from app.schemas.common import HandoffType
from app.schemas.critic import CriticFeedback


class ResearchToAnalystHandoff(BaseModel):
    handoff_id: str
    handoff_type: HandoffType = HandoffType.RESEARCH_TO_ANALYST
    evidence_ids: list[str] = Field(default_factory=list)
    research_questions_covered: list[str] = Field(default_factory=list)
    research_questions_unanswered: list[str] = Field(default_factory=list)
    notes: str = ""


class AnalystToCriticHandoff(BaseModel):
    handoff_id: str
    handoff_type: HandoffType = HandoffType.ANALYST_TO_CRITIC
    analysis: AnalysisResult
    revision_round: int = 0


class CriticToSupervisorHandoff(BaseModel):
    handoff_id: str
    handoff_type: HandoffType = HandoffType.CRITIC_TO_SUPERVISOR
    feedback: CriticFeedback


class SupervisorToWriterHandoff(BaseModel):
    handoff_id: str
    handoff_type: HandoffType = HandoffType.SUPERVISOR_TO_WRITER
    analysis: AnalysisResult
    critic_feedback: CriticFeedback
    decision_notes: str = Field(
        default="", description="Supervisor's rationale for releasing this analysis to the Writer."
    )
