"""Analyst Agent.

Responsibilities: compare findings, detect patterns, build comparisons, and
generate insights — working ONLY from the evidence collected by the
Research Agent. Never introduces outside knowledge.
"""

from __future__ import annotations

from app.agents.base import format_evidence_lines
from app.prompts.loader import render_prompt
from app.schemas.analysis import AnalysisResult
from app.schemas.critic import CriticFeedback
from app.schemas.evidence import EvidenceItem
from app.services.llm_service import LLMCallResult, get_llm_service

_SYSTEM_PROMPT = (
    "You are the Analyst Agent inside Evident. You reason strictly from the "
    "evidence you are given — never from general knowledge or assumptions. "
    "If evidence is insufficient, state that explicitly instead of "
    "speculating."
)


def _format_revision_context(feedback: CriticFeedback | None) -> str:
    if feedback is None:
        return ""
    revisions = "\n".join(f"- {item}" for item in feedback.required_revisions) or "(none listed)"
    return (
        "## Critic feedback from the previous round — you MUST address this\n\n"
        f"Rationale: {feedback.rationale}\n\n"
        f"Required revisions:\n{revisions}"
    )


async def analyze_evidence(
    *,
    objective: str,
    research_questions: list[str],
    comparison_criteria: list[str],
    evidence: list[EvidenceItem],
    prior_feedback: CriticFeedback | None,
) -> tuple[AnalysisResult, LLMCallResult]:
    prompt = render_prompt(
        "analyst/analysis.md",
        objective=objective,
        research_questions=research_questions,
        comparison_criteria=comparison_criteria,
        evidence_lines=format_evidence_lines(evidence),
        revision_context=_format_revision_context(prior_feedback),
    )
    llm = get_llm_service()
    result, meta = await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
        response_model=AnalysisResult,
    )

    # Defensively drop citations to evidence_ids that don't actually exist —
    # the Critic will also catch this, but there is no reason to let an
    # obviously-fabricated citation through when it's cheap to filter here.
    valid_ids = {item.evidence_id for item in evidence}
    for insight in result.insights:
        insight.supporting_evidence_ids = [eid for eid in insight.supporting_evidence_ids if eid in valid_ids]
    for row in result.comparisons:
        row.evidence_ids = [eid for eid in row.evidence_ids if eid in valid_ids]
    result.evidence_ids_used = [eid for eid in result.evidence_ids_used if eid in valid_ids]

    return result, meta
