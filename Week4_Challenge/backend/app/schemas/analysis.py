"""Analyst output schemas. The Analyst works ONLY from evidence — every
insight and comparison row must cite evidence_ids."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ComparisonRow(BaseModel):
    criterion: str
    entity: str
    finding: str
    evidence_ids: list[str] = Field(default_factory=list)


class Insight(BaseModel):
    title: str
    explanation: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    confidence: int = Field(..., ge=0, le=100)


class AnalysisResult(BaseModel):
    summary: str = Field(..., description="High-level synthesis of the evidence.")
    insights: list[Insight] = Field(default_factory=list)
    comparisons: list[ComparisonRow] = Field(default_factory=list)
    patterns_detected: list[str] = Field(default_factory=list)
    unsupported_gaps: list[str] = Field(
        default_factory=list, description="Questions the evidence could not answer."
    )
    evidence_ids_used: list[str] = Field(default_factory=list)


class BonusInsight(BaseModel):
    """Output shape shared by the optional Fact Checker, Risk Analyst,
    Competitor Analysis, and Strategy agents."""

    agent: str
    title: str
    content: str
    evidence_ids: list[str] = Field(default_factory=list)
    severity: str | None = Field(default=None, description="For risk-oriented agents: low/medium/high/critical.")
