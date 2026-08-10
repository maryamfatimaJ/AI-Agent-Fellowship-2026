"""Critic Agent output schema. The Critic evaluates and verdicts — it never
rewrites the analysis itself."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import CriticVerdict


class CriticFeedback(BaseModel):
    verdict: CriticVerdict
    evidence_coverage_score: int = Field(..., ge=0, le=100)
    logical_consistency_score: int = Field(..., ge=0, le=100)
    completeness_score: int = Field(..., ge=0, le=100)
    relevance_score: int = Field(..., ge=0, le=100)
    unsupported_claims: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    weak_reasoning: list[str] = Field(default_factory=list)
    required_revisions: list[str] = Field(
        default_factory=list, description="Specific, actionable changes the Analyst must make to pass."
    )
    rationale: str = Field(..., description="Why this verdict was reached.")
    revision_round: int = 0
