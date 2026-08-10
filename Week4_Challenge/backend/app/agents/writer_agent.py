"""Report Writer Agent.

Responsibilities: produce the final report, preserve citations, and keep
evidence strictly separate from recommendation.
"""

from __future__ import annotations

from app.prompts.loader import render_prompt
from app.schemas.analysis import AnalysisResult, BonusInsight
from app.schemas.critic import CriticFeedback
from app.schemas.evidence import EvidenceItem
from app.schemas.report import FinalReport
from app.services.llm_service import LLMCallResult, get_llm_service
from app.tools.citation_validator_tool import validate_citations

_SYSTEM_PROMPT = (
    "You are the Report Writer Agent inside Evident. You compile an "
    "already-approved analysis into a polished, evidence-grounded decision "
    "brief. You do not introduce new claims, and you keep evidence and "
    "recommendation in clearly separate sections."
)


def _format_evidence_lines(evidence: list[EvidenceItem]) -> list[str]:
    if not evidence:
        return ["(no evidence available)"]
    return [
        f"{item.evidence_id} · {item.evidence_type.value} · {item.confidence}% · {item.claim} · {item.source}"
        for item in evidence
    ]


async def write_report(
    *,
    objective: str,
    deliverable: str,
    analysis: AnalysisResult,
    critic_feedback: CriticFeedback,
    evidence: list[EvidenceItem],
    bonus_insights: list[BonusInsight],
    human_feedback: str | None = None,
) -> tuple[FinalReport, LLMCallResult]:
    prompt = render_prompt(
        "writer/report_writing.md",
        objective=objective,
        deliverable=deliverable,
        analysis_summary=analysis.summary,
        analysis_insights=[f"{i.title}: {i.explanation} [{','.join(i.supporting_evidence_ids)}]" for i in analysis.insights]
        or ["(none)"],
        analysis_comparisons=[f"{c.criterion} / {c.entity}: {c.finding} [{','.join(c.evidence_ids)}]" for c in analysis.comparisons]
        or ["(none)"],
        analysis_patterns=analysis.patterns_detected or ["(none)"],
        critic_notes=f"{critic_feedback.rationale}\nRemaining caveats: {critic_feedback.required_revisions or 'none'}",
        bonus_notes=[f"**{b.title}** ({b.agent}): {b.content}" for b in bonus_insights] or ["(none)"],
        evidence_lines=_format_evidence_lines(evidence),
        human_feedback=human_feedback,
    )
    llm = get_llm_service()
    report, meta = await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
        response_model=FinalReport,
    )

    valid_ids = [item.evidence_id for item in evidence]
    all_text = " ".join(section.body_markdown for section in report.evidence_sections) + " " + " ".join(report.citations)
    validation = validate_citations(all_text, valid_ids)
    report.citations = list(dict.fromkeys(report.citations + validation.cited_ids))

    report.markdown = _render_markdown(report)
    return report, meta


def _render_markdown(report: FinalReport) -> str:
    lines = [f"# {report.title}", "", "## Executive Summary", "", report.executive_summary, ""]

    lines.append("## Evidence")
    lines.append("")
    for section in report.evidence_sections:
        lines.append(f"### {section.heading}")
        lines.append("")
        lines.append(section.body_markdown)
        lines.append("")

    lines.append("## Recommendation")
    lines.append("")
    lines.append(report.recommendation)
    lines.append("")

    if report.caveats:
        lines.append("## Caveats")
        lines.append("")
        for caveat in report.caveats:
            lines.append(f"- {caveat}")
        lines.append("")

    if report.citations:
        lines.append("## Citations")
        lines.append("")
        for citation in report.citations:
            lines.append(f"- `{citation}`")
        lines.append("")

    return "\n".join(lines)
