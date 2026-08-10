"""The Evidence model — the single source of truth every downstream agent
(Analyst, Critic, Writer) must trace claims back to."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import EvidenceType


class EvidenceItem(BaseModel):
    evidence_id: str
    claim: str = Field(..., description="The specific claim or data point extracted.")
    evidence_type: EvidenceType = Field(
        default=EvidenceType.CLAIM,
        description="Whether this is a verified fact, an unverified claim, an assumption, or a flagged information gap.",
    )
    supporting_text: str = Field(..., description="The verbatim (or lightly trimmed) excerpt supporting the claim.")
    source: str = Field(..., description="The source URL or identifier.")
    source_title: str = Field(..., description="Human-readable title of the source.")
    retrieved_at: str = Field(..., description="ISO-8601 timestamp when this evidence was retrieved.")
    research_question: str = Field(..., description="Which research question this evidence answers.")
    confidence: int = Field(..., ge=0, le=100, description="Agent-assessed confidence in this evidence, 0-100.")
    agent_id: str = Field(..., description="The agent (and task) that produced this evidence.")
    task_id: str | None = Field(default=None)


class EvidenceDraft(BaseModel):
    """The subset of EvidenceItem the Research Agent's LLM call is allowed to
    produce. Identity/provenance fields (evidence_id, retrieved_at, agent_id,
    task_id, research_question) are assigned deterministically by our own
    code afterward — never trusted from model output."""

    claim: str
    evidence_type: EvidenceType = EvidenceType.CLAIM
    supporting_text: str
    source: str
    source_title: str
    confidence: int = Field(..., ge=0, le=100)
