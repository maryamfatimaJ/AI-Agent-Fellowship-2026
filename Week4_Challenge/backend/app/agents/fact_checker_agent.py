"""Fact Checker Agent (bonus). Runs in parallel with the other specialists
after the Analyst produces its analysis; flags factual precision issues
without redoing the Analyst's synthesis."""

from __future__ import annotations

from app.agents.base import format_evidence_lines
from app.prompts.loader import render_prompt
from app.schemas.analysis import AnalysisResult, BonusInsight
from app.schemas.evidence import EvidenceItem
from app.services.llm_service import LLMCallResult, get_llm_service

_SYSTEM_PROMPT = (
    "You are the Fact Checker Agent inside Evident, a bonus specialist "
    "focused narrowly on factual precision. Ground every finding in the "
    "evidence provided; never speculate."
)


async def check_facts(*, analysis: AnalysisResult, evidence: list[EvidenceItem]) -> tuple[BonusInsight, LLMCallResult]:
    prompt = render_prompt(
        "fact_checker/fact_check.md",
        analysis_summary=analysis.summary,
        evidence_lines=format_evidence_lines(evidence),
    )
    llm = get_llm_service()
    result, meta = await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
        response_model=BonusInsight,
    )
    result.agent = "fact_checker"
    return result, meta
