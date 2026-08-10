"""Final Report Writer output. Evidence and recommendation are kept in
distinct sections so a reader can separate "what we found" from "what we
suggest doing about it"."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReportSection(BaseModel):
    heading: str
    body_markdown: str
    evidence_ids: list[str] = Field(default_factory=list)


class FinalReport(BaseModel):
    title: str
    executive_summary: str
    evidence_sections: list[ReportSection] = Field(
        default_factory=list, description="Findings, kept strictly separate from recommendations."
    )
    recommendation: str = Field(..., description="The decision recommendation, clearly separated from evidence.")
    caveats: list[str] = Field(default_factory=list, description="Known gaps, conflicts, or low-confidence areas.")
    citations: list[str] = Field(default_factory=list, description="evidence_ids cited anywhere in the report.")
    markdown: str = Field(default="", description="The fully rendered markdown document.")
    approval_status: str = Field(default="pending")
