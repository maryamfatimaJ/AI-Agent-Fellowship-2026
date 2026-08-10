"""Risk Analyst Agent (bonus). Runs in parallel with the other specialists
after the Analyst produces its analysis; surfaces risks grounded in the
evidence."""

from __future__ import annotations

from app.agents.base import format_evidence_lines
from app.prompts.loader import render_prompt
from app.schemas.analysis import AnalysisResult, BonusInsight
from app.schemas.evidence import EvidenceItem
from app.services.llm_service import LLMCallResult, get_llm_service

_SYSTEM_PROMPT = (
    "You are the Risk Analyst Agent inside Evident, a bonus specialist "
    "focused on regulatory, competitive, financial, operational, and "
    "reputational risk. Ground every risk in the evidence provided."
)


async def analyze_risk(
    *, objective: str, analysis: AnalysisResult, evidence: list[EvidenceItem]
) -> tuple[BonusInsight, LLMCallResult]:
    prompt = render_prompt(
        "risk_analyst/risk_analysis.md",
        objective=objective,
        analysis_summary=analysis.summary,
        evidence_lines=format_evidence_lines(evidence),
    )
    llm = get_llm_service()
    result, meta = await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
        response_model=BonusInsight,
    )
    result.agent = "risk_analyst"
    return result, meta
