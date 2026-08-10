"""Strategy Agent (bonus). Runs in parallel with the other specialists after
the Analyst produces its analysis; proposes strategic options grounded in
the evidence for the Writer to consider."""

from __future__ import annotations

from app.agents.base import format_evidence_lines
from app.prompts.loader import render_prompt
from app.schemas.analysis import AnalysisResult, BonusInsight
from app.schemas.evidence import EvidenceItem
from app.services.llm_service import LLMCallResult, get_llm_service

_SYSTEM_PROMPT = (
    "You are the Strategy Agent inside Evident, a bonus specialist. Propose "
    "strategic options implied by the evidence — never generic advice "
    "disconnected from what was actually found."
)


async def propose_strategy(
    *, objective: str, deliverable: str, analysis: AnalysisResult, evidence: list[EvidenceItem]
) -> tuple[BonusInsight, LLMCallResult]:
    prompt = render_prompt(
        "strategy/strategy.md",
        objective=objective,
        deliverable=deliverable,
        analysis_summary=analysis.summary,
        evidence_lines=format_evidence_lines(evidence),
    )
    llm = get_llm_service()
    result, meta = await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
        response_model=BonusInsight,
    )
    result.agent = "strategy"
    return result, meta
