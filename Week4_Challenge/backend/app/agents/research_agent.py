"""Research Agent.

Responsibilities: search, collect evidence, extract findings, and store
evidence — while explicitly distinguishing facts, claims, assumptions, and
missing information. Runs once per independent task, fanned out in
parallel by the graph.
"""

from __future__ import annotations

from app.prompts.loader import render_prompt
from app.schemas.evidence import EvidenceItem
from app.schemas.research import EvidenceSynthesisResult, SearchQueryPlan
from app.schemas.task import ResearchTask
from app.services.llm_service import LLMCallResult, get_llm_service
from app.tools.content_extraction_tool import extract_content
from app.tools.search_tool import search_web
from app.utils.errors import EvidentError
from app.utils.ids import new_evidence_id
from app.utils.time_utils import utc_now_iso

_SYSTEM_PROMPT = (
    "You are the Research Agent inside Evident. You gather and structure "
    "evidence — you never analyze, compare, or draw conclusions; that is "
    "the Analyst Agent's job. Never fabricate a source, quote, or number."
)

_MAX_SEARCH_RESULTS = 5
_MAX_PAGES_TO_FETCH = 4


class ResearchTaskOutcome:
    """Plain result container returned by `execute_research_task` (kept as a
    simple class, not a Pydantic model, since it also carries non-serializable
    call metadata used only for logging)."""

    def __init__(
        self,
        *,
        evidence: list[EvidenceItem],
        queries_used: list[str],
        sources_fetched: list[str],
        llm_calls: list[LLMCallResult],
        tool_errors: list[str],
    ) -> None:
        self.evidence = evidence
        self.queries_used = queries_used
        self.sources_fetched = sources_fetched
        self.llm_calls = llm_calls
        self.tool_errors = tool_errors


async def execute_research_task(task: ResearchTask, *, comparison_criteria: list[str]) -> ResearchTaskOutcome:
    llm = get_llm_service()
    tool_errors: list[str] = []

    query_prompt = render_prompt(
        "research/query_generation.md",
        task_description=task.description,
        research_question=task.research_question,
        entity=task.entity,
        comparison_criteria=comparison_criteria,
    )
    query_plan, query_meta = await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=query_prompt,
        response_model=SearchQueryPlan,
    )
    llm_calls = [query_meta]

    search_results = []
    for query in query_plan.queries:
        try:
            results = await search_web(query, max_results=_MAX_SEARCH_RESULTS)
            search_results.extend(results)
        except EvidentError as exc:
            tool_errors.append(f"search failed for {query!r}: {exc.message}")

    # De-duplicate by URL, keep the top N to fetch full content for.
    seen_urls: set[str] = set()
    unique_results = []
    for result in search_results:
        if result.url and result.url not in seen_urls:
            seen_urls.add(result.url)
            unique_results.append(result)

    fetched_pages = []
    sources_fetched: list[str] = []
    for result in unique_results[:_MAX_PAGES_TO_FETCH]:
        try:
            content = await extract_content(result.url)
            fetched_pages.append((result, content))
            sources_fetched.append(result.url)
        except EvidentError as exc:
            tool_errors.append(f"extraction failed for {result.url}: {exc.message}")

    if not fetched_pages:
        # No page content — fall back to search snippets so the agent can
        # still produce (low-confidence) evidence or a missing_information item.
        excerpt_lines = [f"[{r.title}]({r.url})\n{r.snippet}" for r in unique_results[:_MAX_PAGES_TO_FETCH]]
    else:
        excerpt_lines = [f"[{r.title}]({r.url})\n{c.text[:2500]}" for r, c in fetched_pages]

    synthesis_prompt = render_prompt(
        "research/evidence_synthesis.md",
        task_description=task.description,
        research_question=task.research_question,
        entity=task.entity,
        source_excerpts=excerpt_lines if excerpt_lines else ["(no sources retrieved)"],
    )
    synthesis, synthesis_meta = await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=synthesis_prompt,
        response_model=EvidenceSynthesisResult,
    )
    llm_calls.append(synthesis_meta)

    now = utc_now_iso()
    evidence = [
        EvidenceItem(
            evidence_id=new_evidence_id(),
            claim=draft.claim,
            evidence_type=draft.evidence_type,
            supporting_text=draft.supporting_text,
            source=draft.source,
            source_title=draft.source_title,
            retrieved_at=now,
            research_question=task.research_question,
            confidence=draft.confidence,
            agent_id="research",
            task_id=task.task_id,
        )
        for draft in synthesis.items
    ]

    return ResearchTaskOutcome(
        evidence=evidence,
        queries_used=query_plan.queries,
        sources_fetched=sources_fetched,
        llm_calls=llm_calls,
        tool_errors=tool_errors,
    )
