"""Competitor Analysis Agent (bonus). Runs in parallel with the other
specialists after the Analyst produces its analysis; summarizes the
competitive landscape when the evidence supports it."""

from __future__ import annotations

from app.agents.base import format_evidence_lines
from app.prompts.loader import render_prompt
from app.schemas.analysis import AnalysisResult, BonusInsight
from app.schemas.evidence import EvidenceItem
from app.services.llm_service import LLMCallResult, get_llm_service

_SYSTEM_PROMPT = (
    "You are the Competitor Analysis Agent inside Evident, a bonus "
    "specialist. Summarize the competitive landscape strictly from the "
    "evidence provided; state plainly if no competitive information exists."
)


async def analyze_competitors(
    *, objective: str, entities: list[str], analysis: AnalysisResult, evidence: list[EvidenceItem]
) -> tuple[BonusInsight, LLMCallResult]:
    prompt = render_prompt(
        "competitor_analysis/competitor_analysis.md",
        objective=objective,
        entities=entities,
        analysis_summary=analysis.summary,
        evidence_lines=format_evidence_lines(evidence),
    )
    llm = get_llm_service()
    result, meta = await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
        response_model=BonusInsight,
    )
    result.agent = "competitor_analysis"
    return result, meta
