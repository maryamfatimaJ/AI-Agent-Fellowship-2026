from app.evaluation.agent_metrics import AgentCaseMetrics, aggregate_agent_metrics, evaluate_agent_case
from app.evaluation.dataset import EvalCase
from app.evaluation.rag_metrics import RagCaseMetrics, aggregate_rag_metrics, evaluate_rag_case


def _rag_case(**overrides):
    defaults = dict(test_id="r01", category="rag", user_input="x", expected_source="policy_refund.txt", expected_keywords=["30 days"])
    defaults.update(overrides)
    return EvalCase(**defaults)


def test_evaluate_rag_case_hit_and_grounded():
    case = _rag_case()
    context = [{"filename": "policy_refund.txt", "snippet": "Refunds within 30 days."}]
    metrics = evaluate_rag_case(case, "You have 30 days to request a refund.", context)
    assert metrics.retrieval_hit is True
    assert metrics.citation_correctness is True
    assert metrics.unsupported_claim is False
    assert metrics.failure_classification == "success"


def test_evaluate_rag_case_retrieval_failure():
    case = _rag_case()
    metrics = evaluate_rag_case(case, "I'm not sure.", rag_context=[])
    assert metrics.retrieval_hit is False
    assert metrics.failure_classification == "retrieval_failure"


def test_evaluate_rag_case_generation_failure():
    case = _rag_case()
    context = [{"filename": "policy_refund.txt", "snippet": "Refunds within 30 days."}]
    metrics = evaluate_rag_case(case, "I don't know the refund window.", context)
    assert metrics.retrieval_hit is True
    assert metrics.failure_classification == "generation_failure"
    assert metrics.unsupported_claim is True


def test_evaluate_rag_case_non_rag_case_returns_empty_metrics():
    case = EvalCase(test_id="n01", category="normal", user_input="x")
    metrics = evaluate_rag_case(case, "anything", [])
    assert metrics.retrieval_hit is None


def test_evaluate_rag_case_without_expected_keywords_is_unclassified():
    """A RAG case with no expected_keywords has no way to check whether the
    generated answer is actually correct — this must be labeled honestly as
    'unclassified', never silently counted as a success."""
    case = _rag_case(expected_keywords=[])
    context = [{"filename": "policy_refund.txt", "snippet": "Refunds within 30 days."}]
    metrics = evaluate_rag_case(case, "Some answer.", context)
    assert metrics.failure_classification == "unclassified"


def test_aggregate_rag_metrics():
    metrics = [
        RagCaseMetrics(retrieval_hit=True, context_relevance=1.0, citation_correctness=True, unsupported_claim=False, failure_classification=None),
        RagCaseMetrics(retrieval_hit=False, context_relevance=0.0, citation_correctness=False, unsupported_claim=None, failure_classification="retrieval_failure"),
    ]
    summary = aggregate_rag_metrics(metrics)
    assert summary["n_cases"] == 2
    assert summary["retrieval_hit_rate"] == 0.5
    assert summary["retrieval_failures"] == 1


def _tool_case(**overrides):
    defaults = dict(
        test_id="t01", category="tool_use", user_input="x",
        expected_tool="search_documents", expected_args={"query": "refund"},
    )
    defaults.update(overrides)
    return EvalCase(**defaults)


def test_evaluate_agent_case_correct_tool_and_args():
    case = _tool_case()
    steps = [{"tool": "search_documents", "arguments": {"query": "refund policy"}, "error": None}]
    metrics = evaluate_agent_case(case, steps, hit_loop_limit=False, pending_action_id=None, final_text="Here it is.")
    assert metrics.tool_selection_correct is True
    assert metrics.tool_arguments_correct is True
    assert metrics.task_completed is True


def test_evaluate_agent_case_wrong_tool():
    case = _tool_case()
    steps = [{"tool": "save_memory", "arguments": {"key": "x", "value": "y"}, "error": None}]
    metrics = evaluate_agent_case(case, steps, hit_loop_limit=False, pending_action_id=None, final_text="Saved.")
    assert metrics.tool_selection_correct is False
    assert metrics.task_completed is False


def test_evaluate_agent_case_requires_approval():
    case = _tool_case(expected_tool="delete_document", expected_args={"document_id": "doc-1"}, expected_behavior="requires_approval")
    steps = [{"tool": "delete_document", "arguments": {"document_id": "doc-1"}, "error": "awaiting_approval"}]
    metrics = evaluate_agent_case(case, steps, hit_loop_limit=False, pending_action_id="pa-1", final_text="Needs approval.")
    assert metrics.required_approval_correctly is True
    assert metrics.task_completed is True


def test_evaluate_agent_case_recovers_from_tool_error():
    case = _tool_case()
    steps = [{"tool": "search_documents", "arguments": {"query": "refund"}, "error": "boom"}]
    metrics = evaluate_agent_case(case, steps, hit_loop_limit=False, pending_action_id=None, final_text="Here's a direct answer instead.")
    assert metrics.recovered_from_error is True


def test_aggregate_agent_metrics():
    metrics = [
        AgentCaseMetrics(tool_selection_correct=True, tool_arguments_correct=True, task_completed=True, loop_count=1, hit_loop_limit=False),
        AgentCaseMetrics(tool_selection_correct=False, tool_arguments_correct=False, task_completed=False, loop_count=5, hit_loop_limit=True),
    ]
    summary = aggregate_agent_metrics(metrics)
    assert summary["n_cases"] == 2
    assert summary["tool_selection_accuracy"] == 0.5
    assert summary["loop_limit_hit_rate"] == 0.5
