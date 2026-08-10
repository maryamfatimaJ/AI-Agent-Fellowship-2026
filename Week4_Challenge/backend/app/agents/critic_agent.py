"""Critic Agent.

Responsibilities: evaluate the Analyst's output for evidence coverage,
logical consistency, completeness, unsupported claims, and contradictions.
Approves or rejects — never rewrites the analysis.
"""

from __future__ import annotations

from app.agents.base import format_evidence_lines
from app.prompts.loader import render_prompt
from app.schemas.analysis import AnalysisResult
from app.schemas.critic import CriticFeedback
from app.schemas.evidence import EvidenceItem
from app.services.llm_service import LLMCallResult, get_llm_service
from app.tools.citation_validator_tool import validate_citations

_SYSTEM_PROMPT = (
    "You are the Critic Agent inside Evident. You adversarially evaluate — "
    "you never rewrite the analysis yourself. Be strict: your job is to "
    "catch overclaiming, contradictions, and weak reasoning before a human "
    "decision-maker ever sees this analysis."
)


async def critique_analysis(
    *,
    objective: str,
    comparison_criteria: list[str],
    evidence: list[EvidenceItem],
    analysis: AnalysisResult,
    revision_round: int,
) -> tuple[CriticFeedback, LLMCallResult]:
    prompt = render_prompt(
        "critic/critic_review.md",
        objective=objective,
        comparison_criteria=comparison_criteria,
        evidence_lines=format_evidence_lines(evidence),
        analysis_summary=analysis.summary,
        analysis_insights=[f"{i.title}: {i.explanation} (cites {i.supporting_evidence_ids})" for i in analysis.insights]
        or ["(none)"],
        analysis_comparisons=[f"{c.criterion} / {c.entity}: {c.finding} (cites {c.evidence_ids})" for c in analysis.comparisons]
        or ["(none)"],
        analysis_patterns=analysis.patterns_detected or ["(none)"],
        analysis_gaps=analysis.unsupported_gaps or ["(none)"],
        analysis_evidence_ids=analysis.evidence_ids_used or ["(none)"],
    )
    llm = get_llm_service()
    feedback, meta = await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
        response_model=CriticFeedback,
    )
    feedback.revision_round = revision_round

    # Deterministic backstop: independently verify every cited evidence_id
    # actually exists, regardless of what the LLM concluded. This guarantees
    # hallucinated citations are always caught, even if the Critic's own
    # judgement missed them.
    valid_ids = [item.evidence_id for item in evidence]
    all_cited_text = " ".join(
        analysis.evidence_ids_used
        + [eid for i in analysis.insights for eid in i.supporting_evidence_ids]
        + [eid for c in analysis.comparisons for eid in c.evidence_ids]
    )
    validation = validate_citations(all_cited_text, valid_ids)
    if not validation.is_valid:
        feedback.unsupported_claims = list(dict.fromkeys(feedback.unsupported_claims + validation.invalid_ids))
        feedback.verdict = feedback.verdict.__class__.REJECTED

    return feedback, meta
