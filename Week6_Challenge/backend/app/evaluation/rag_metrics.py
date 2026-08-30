"""RAG-specific evaluation metrics: retrieval hit rate, context relevance,
citation correctness, an unsupported-claim heuristic, and groundedness (from
the LLM judge when available), plus a rule-based retrieval-vs-generation
failure classification. Computed per case by the runner, aggregated here.

RAG is never scored only from the final answer: `failure_classification` is
always one of exactly three states —

    question -> was the correct chunk retrieved?
        no  -> "retrieval_failure"
        yes -> was the correct answer generated from it?
            no  -> "generation_failure"
            yes -> "success"

(a fourth state, "unclassified", covers cases with no expected_keywords to
check the answer against — genuinely not evaluable this way, not silently
counted as a success).
"""

from dataclasses import dataclass

from app.evaluation.dataset import EvalCase
from app.evaluation.deterministic_evaluators import retrieval_hit


@dataclass
class RagCaseMetrics:
    retrieval_hit: bool | None = None
    context_relevance: float | None = None
    citation_correctness: bool | None = None
    groundedness_score: float | None = None
    unsupported_claim: bool | None = None
    failure_classification: str | None = None


def evaluate_rag_case(
    case: EvalCase,
    actual_output: str,
    rag_context: list[dict] | None,
    judge_result: dict | None = None,
) -> RagCaseMetrics:
    if case.expected_source is None:
        return RagCaseMetrics()

    hit = retrieval_hit(rag_context, case.expected_source)
    citations = rag_context or []
    citation_correct = any(c.get("filename") == case.expected_source for c in citations)

    if citations:
        relevance = sum(1 for c in citations if c.get("filename") == case.expected_source) / len(citations)
    else:
        relevance = 0.0

    answer_has_expected_keywords = (
        any(kw.lower() in actual_output.lower() for kw in case.expected_keywords) if case.expected_keywords else None
    )

    unsupported = None
    if case.expected_keywords:
        # Proxy for hallucination: relevant context WAS retrieved, but the answer
        # doesn't reflect any of the facts we expected it to ground on.
        unsupported = bool(hit) and answer_has_expected_keywords is False

    groundedness = None
    if judge_result and judge_result.get("groundedness") is not None:
        groundedness = judge_result["groundedness"] / 5.0

    if answer_has_expected_keywords is None:
        failure_classification = "unclassified"
    elif answer_has_expected_keywords is False:
        failure_classification = "retrieval_failure" if not hit else "generation_failure"
    else:
        failure_classification = "success"

    return RagCaseMetrics(
        retrieval_hit=hit,
        context_relevance=round(relevance, 3),
        citation_correctness=citation_correct,
        groundedness_score=groundedness,
        unsupported_claim=unsupported,
        failure_classification=failure_classification,
    )


def aggregate_rag_metrics(per_case: list[RagCaseMetrics]) -> dict:
    applicable = [m for m in per_case if m.retrieval_hit is not None]
    if not applicable:
        return {}

    def _avg(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 3) if values else None

    relevance_values = [m.context_relevance for m in applicable if m.context_relevance is not None]
    groundedness_values = [m.groundedness_score for m in applicable if m.groundedness_score is not None]
    unsupported_values = [m.unsupported_claim for m in applicable if m.unsupported_claim is not None]
    citation_values = [m.citation_correctness for m in applicable if m.citation_correctness is not None]

    return {
        "n_cases": len(applicable),
        "retrieval_hit_rate": _avg([1.0 if m.retrieval_hit else 0.0 for m in applicable]),
        "avg_context_relevance": _avg(relevance_values),
        "avg_groundedness": _avg(groundedness_values),
        "citation_correctness_rate": _avg([1.0 if c else 0.0 for c in citation_values]) if citation_values else None,
        "unsupported_claim_rate": _avg([1.0 if u else 0.0 for u in unsupported_values]) if unsupported_values else None,
        "successes": sum(1 for m in applicable if m.failure_classification == "success"),
        "retrieval_failures": sum(1 for m in applicable if m.failure_classification == "retrieval_failure"),
        "generation_failures": sum(1 for m in applicable if m.failure_classification == "generation_failure"),
        "unclassified": sum(1 for m in applicable if m.failure_classification == "unclassified"),
    }
