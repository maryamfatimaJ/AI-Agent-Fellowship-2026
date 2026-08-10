"""Research Agent intermediate schemas — the LLM-facing shapes used during
query generation and evidence synthesis, before evidence is stamped with
deterministic identity/provenance fields."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.evidence import EvidenceDraft


class SearchQueryPlan(BaseModel):
    queries: list[str] = Field(..., min_length=1, max_length=3)


class EvidenceSynthesisResult(BaseModel):
    items: list[EvidenceDraft] = Field(default_factory=list)
