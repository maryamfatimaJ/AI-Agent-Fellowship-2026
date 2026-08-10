"""Shared pytest fixtures.

No test in this suite ever calls a real LLM provider or the live network —
`fake_llm_service` stubs `LLMService.generate_structured` with canned
responses keyed by the requested Pydantic model, and tools that hit the
network are monkeypatched at their call sites where relevant.
"""

from __future__ import annotations

import pytest

from app.models import run_store
from app.services import evidence_service
from app.services.llm_service import LLMCallResult


@pytest.fixture(autouse=True)
def _reset_process_wide_stores():
    """Every run/evidence store is a module-level dict — clear it between
    tests so runs from one test can never leak into another."""

    run_store._REGISTRY.clear()
    evidence_service._STORE.clear()
    yield
    run_store._REGISTRY.clear()
    evidence_service._STORE.clear()


class FakeLLMService:
    """Drop-in replacement for LLMService that returns pre-scripted
    responses keyed by response_model, instead of calling a real provider.

    A mapped value may be a single model instance (returned on every call)
    or a list of instances (popped in order — for tests where the same
    model type is requested more than once, e.g. across revision rounds)."""

    def __init__(self, responses: dict[type, object]) -> None:
        self._responses = responses
        self.calls: list[type] = []

    async def generate_structured(self, *, system_prompt: str, user_prompt: str, response_model: type):
        self.calls.append(response_model)
        if response_model not in self._responses:
            raise AssertionError(f"FakeLLMService has no scripted response for {response_model.__name__}")
        value = self._responses[response_model]
        instance = value.pop(0) if isinstance(value, list) else value
        return instance, LLMCallResult(provider="fake", model="fake-model", attempts=1, duration_ms=1)


@pytest.fixture
def fake_llm(monkeypatch):
    """Patch `get_llm_service` everywhere it's imported to return a
    FakeLLMService. Returns the factory so tests can install responses:

        service = fake_llm({SearchQueryPlan: SearchQueryPlan(queries=["q"])})
    """

    def _install(responses: dict[type, object]) -> FakeLLMService:
        fake = FakeLLMService(responses)
        for module_path in [
            "app.agents.supervisor_agent",
            "app.agents.research_agent",
            "app.agents.analyst_agent",
            "app.agents.critic_agent",
            "app.agents.writer_agent",
            "app.agents.fact_checker_agent",
            "app.agents.risk_analyst_agent",
            "app.agents.competitor_analysis_agent",
            "app.agents.strategy_agent",
        ]:
            monkeypatch.setattr(f"{module_path}.get_llm_service", lambda: fake)
        return fake

    return _install


@pytest.fixture
def patch_external_tools(monkeypatch):
    """Patch every tool call that would otherwise hit the network or disk,
    so graph/API integration tests are fully hermetic."""

    from app.tools.content_extraction_tool import ExtractedContent
    from app.tools.search_tool import SearchResult

    async def fake_search_web(query: str, max_results: int = 5):
        return [SearchResult(title=f"Result for {query}", url="https://example.com/a", snippet="snippet")]

    async def fake_extract_content(url: str, *, max_chars: int = 6000):
        return ExtractedContent(url=url, title="Example", text="Example page body text about the topic.")

    async def fake_export_markdown(run_id: str, markdown: str):
        from pathlib import Path

        return Path(f"/fake/reports/{run_id}.md")

    monkeypatch.setattr("app.agents.research_agent.search_web", fake_search_web)
    monkeypatch.setattr("app.agents.research_agent.extract_content", fake_extract_content)
    monkeypatch.setattr("app.graph.nodes.writer_nodes.export_markdown", fake_export_markdown)


@pytest.fixture
def happy_path_llm(fake_llm, patch_external_tools):
    """Factory fixture: scripts every LLM call needed for a full, two-task,
    critic-approves-on-first-pass run through the entire graph — the
    control-flow happy path used by the graph/API integration tests.

    Call it with no arguments for the default non-ambiguous scenario, or
    pass `structured_request=` (a single instance or a list, for the
    clarification-round test) to override just that part of the script.

    Citation fields are left empty deliberately: evidence_ids are generated
    at runtime (uuid-based) and can't be known ahead of time, and these
    integration tests validate control flow, not citation content (which is
    covered by the focused unit tests in test_agents.py).
    """

    from app.schemas.analysis import AnalysisResult, BonusInsight
    from app.schemas.critic import CriticFeedback
    from app.schemas.evidence import EvidenceDraft
    from app.schemas.report import FinalReport, ReportSection
    from app.schemas.request import StructuredRequest
    from app.schemas.research import EvidenceSynthesisResult, SearchQueryPlan
    from app.schemas.task import ResearchTask, TaskPlan

    default_structured_request = StructuredRequest(
        objective="Decide whether to enter the vertical SaaS market",
        research_questions=["Is the market growing?", "Who are the competitors?"],
        deliverable="decision brief",
        constraints=[],
        comparison_criteria=["growth", "competition"],
        time_horizon="2027",
        missing_information=[],
        is_ambiguous=False,
        clarification_question=None,
        entities=["Product A", "Product B"],
    )

    task_plan = TaskPlan(
        tasks=[
            ResearchTask(
                task_id="t1",
                description="Research market growth",
                research_question="Is the market growing?",
                entity="Product A",
            ),
            ResearchTask(
                task_id="t2",
                description="Research competitors",
                research_question="Who are the competitors?",
                entity="Product B",
            ),
        ],
        rationale="One task per research question.",
    )

    evidence_draft = EvidenceDraft(
        claim="The market grew 19% last year",
        supporting_text="The market grew 19% last year according to the source.",
        source="https://example.com/a",
        source_title="Example",
        confidence=80,
    )

    analysis = AnalysisResult(
        summary="The market is growing and has moderate competition.",
        insights=[],
        comparisons=[],
        patterns_detected=["Growth trend"],
        unsupported_gaps=[],
        evidence_ids_used=[],
    )

    critic_feedback = CriticFeedback(
        verdict="approved",
        evidence_coverage_score=85,
        logical_consistency_score=90,
        completeness_score=85,
        relevance_score=90,
        unsupported_claims=[],
        contradictions=[],
        weak_reasoning=[],
        required_revisions=[],
        rationale="Well supported by the evidence.",
    )

    final_report = FinalReport(
        title="Vertical SaaS Market Entry — Decision Brief",
        executive_summary="The market is growing; entry looks favorable.",
        evidence_sections=[ReportSection(heading="Market growth", body_markdown="The market is growing.")],
        recommendation="Proceed with entry.",
        caveats=[],
        citations=[],
    )

    bonus_insight = lambda agent: BonusInsight(agent=agent, title=f"{agent} notes", content="No issues found.")

    def _install(*, structured_request=None):
        return fake_llm(
            {
                StructuredRequest: structured_request if structured_request is not None else default_structured_request,
                TaskPlan: task_plan,
                SearchQueryPlan: [SearchQueryPlan(queries=["market growth 2027"]) for _ in range(2)],
                EvidenceSynthesisResult: [EvidenceSynthesisResult(items=[evidence_draft]) for _ in range(2)],
                AnalysisResult: analysis,
                CriticFeedback: critic_feedback,
                FinalReport: final_report,
                BonusInsight: [
                    bonus_insight("fact_checker"),
                    bonus_insight("risk_analyst"),
                    bonus_insight("competitor_analysis"),
                    bonus_insight("strategy"),
                ],
            }
        )

    return _install
