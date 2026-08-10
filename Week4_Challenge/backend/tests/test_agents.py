"""Agent-level unit tests. Every LLM call is stubbed via the `fake_llm`
fixture — no test here makes a real network or provider call."""

from __future__ import annotations

from app.agents import supervisor_agent
from app.agents.analyst_agent import analyze_evidence
from app.agents.critic_agent import critique_analysis
from app.agents.research_agent import execute_research_task
from app.schemas.analysis import AnalysisResult, Insight
from app.schemas.critic import CriticFeedback
from app.schemas.evidence import EvidenceDraft, EvidenceItem, EvidenceType
from app.schemas.request import StructuredRequest
from app.schemas.research import EvidenceSynthesisResult, SearchQueryPlan
from app.schemas.task import ResearchTask, TaskPlan


# --- supervisor_agent: deterministic completion decision --------------------


def test_decide_after_critic_advances_on_approval():
    feedback = CriticFeedback(
        verdict="approved",
        evidence_coverage_score=90,
        logical_consistency_score=90,
        completeness_score=90,
        relevance_score=90,
        rationale="Good.",
    )
    decision, _ = supervisor_agent.decide_after_critic(feedback=feedback, revision_count=0, max_revision_cycles=2)
    assert decision == "advance_to_writer"


def test_decide_after_critic_sends_back_when_rejected_and_under_cap():
    feedback = CriticFeedback(
        verdict="rejected",
        evidence_coverage_score=40,
        logical_consistency_score=40,
        completeness_score=40,
        relevance_score=40,
        rationale="Not enough coverage.",
    )
    decision, _ = supervisor_agent.decide_after_critic(feedback=feedback, revision_count=0, max_revision_cycles=2)
    assert decision == "send_back_for_revision"


def test_decide_after_critic_advances_when_revision_cap_reached():
    feedback = CriticFeedback(
        verdict="rejected",
        evidence_coverage_score=40,
        logical_consistency_score=40,
        completeness_score=40,
        relevance_score=40,
        rationale="Still not enough.",
    )
    decision, notes = supervisor_agent.decide_after_critic(feedback=feedback, revision_count=2, max_revision_cycles=2)
    assert decision == "advance_to_writer"
    assert "Maximum revision cycles" in notes


# --- supervisor_agent: request analysis + planning (fake LLM) ---------------


async def test_analyze_request_returns_structured_request(fake_llm):
    expected = StructuredRequest(
        objective="Decide X",
        research_questions=["Is X true?"],
        deliverable="brief",
        is_ambiguous=False,
    )
    fake_llm({StructuredRequest: expected})

    result, meta = await supervisor_agent.analyze_request(
        user_request="Should we do X?", deliverable_hint=None, clarifications=[]
    )

    assert result.objective == "Decide X"
    assert meta.provider == "fake"


async def test_build_task_plan_normalizes_duplicate_and_missing_task_ids(fake_llm):
    raw_plan = TaskPlan(
        tasks=[
            ResearchTask(task_id="", description="d1", research_question="q1"),
            ResearchTask(task_id="dup", description="d2", research_question="q2"),
            ResearchTask(task_id="dup", description="d3", research_question="q3"),
        ]
    )
    fake_llm({TaskPlan: raw_plan})

    structured = StructuredRequest(objective="X", research_questions=["q1", "q2", "q3"], deliverable="brief")
    plan, _ = await supervisor_agent.build_task_plan(structured)

    task_ids = [t.task_id for t in plan.tasks]
    assert len(task_ids) == 3
    assert len(set(task_ids)) == 3  # all unique
    assert all(tid for tid in task_ids)  # none empty
    assert all(t.status.value == "pending" for t in plan.tasks)


# --- analyst_agent: strips citations to nonexistent evidence ----------------


async def test_analyze_evidence_strips_hallucinated_citations(fake_llm):
    evidence = [
        EvidenceItem(
            evidence_id="ev_aaaa0001",
            claim="Real claim",
            supporting_text="Real excerpt",
            source="https://example.com",
            source_title="Example",
            retrieved_at="2026-01-01T00:00:00+00:00",
            research_question="q1",
            confidence=80,
            agent_id="research",
        )
    ]
    hallucinated = AnalysisResult(
        summary="Summary",
        insights=[
            Insight(
                title="Insight",
                explanation="Explanation",
                supporting_evidence_ids=["ev_aaaa0001", "ev_bbbb9999"],
                confidence=70,
            )
        ],
        evidence_ids_used=["ev_aaaa0001", "ev_bbbb9999"],
    )
    fake_llm({AnalysisResult: hallucinated})

    result, _ = await analyze_evidence(
        objective="X",
        research_questions=["q1"],
        comparison_criteria=[],
        evidence=evidence,
        prior_feedback=None,
    )

    assert result.insights[0].supporting_evidence_ids == ["ev_aaaa0001"]
    assert result.evidence_ids_used == ["ev_aaaa0001"]


# --- critic_agent: deterministic citation backstop --------------------------


async def test_critique_analysis_flips_verdict_on_hallucinated_citation(fake_llm):
    evidence = [
        EvidenceItem(
            evidence_id="ev_aaaa0001",
            claim="Real claim",
            supporting_text="Real excerpt",
            source="https://example.com",
            source_title="Example",
            retrieved_at="2026-01-01T00:00:00+00:00",
            research_question="q1",
            confidence=80,
            agent_id="research",
        )
    ]
    analysis = AnalysisResult(
        summary="Summary",
        evidence_ids_used=["ev_aaaa0001", "ev_bbbb9999"],
    )
    approving_feedback = CriticFeedback(
        verdict="approved",
        evidence_coverage_score=90,
        logical_consistency_score=90,
        completeness_score=90,
        relevance_score=90,
        rationale="Looks fine.",
    )
    fake_llm({CriticFeedback: approving_feedback})

    feedback, _ = await critique_analysis(
        objective="X",
        comparison_criteria=[],
        evidence=evidence,
        analysis=analysis,
        revision_round=0,
    )

    assert feedback.verdict.value == "rejected"
    assert "ev_bbbb9999" in feedback.unsupported_claims


# --- research_agent: deterministic evidence stamping ------------------------


async def test_execute_research_task_stamps_deterministic_fields(fake_llm, patch_external_tools):
    fake_llm(
        {
            SearchQueryPlan: SearchQueryPlan(queries=["q1"]),
            EvidenceSynthesisResult: EvidenceSynthesisResult(
                items=[
                    EvidenceDraft(
                        claim="Claim from source",
                        evidence_type=EvidenceType.CLAIM,
                        supporting_text="Excerpt",
                        source="https://example.com/a",
                        source_title="Example",
                        confidence=77,
                    )
                ]
            ),
        }
    )

    task = ResearchTask(task_id="t1", description="Research X", research_question="Is X true?", entity="X")
    outcome = await execute_research_task(task, comparison_criteria=[])

    assert len(outcome.evidence) == 1
    item = outcome.evidence[0]
    assert item.evidence_id.startswith("ev_")
    assert item.task_id == "t1"
    assert item.research_question == "Is X true?"
    assert item.agent_id == "research"
    assert item.confidence == 77
