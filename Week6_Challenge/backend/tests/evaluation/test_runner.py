from app.api.routers.assistants import get_or_create_assistant
from app.evaluation.comparison import compare_runs
from app.evaluation.dataset import EvalCase
from app.evaluation.human_comparison import compare_human_vs_judge
from app.evaluation.runner import run_case, run_evaluation
from app.evaluation.seed import create_eval_workspace, ensure_eval_user
from app.models.document import Document, DocumentStatus
from app.models.evaluation import EvaluationResult
from app.models.workspace import Workspace
from app.services.llm_service import AgentGenerationResult, GenerationResult, ToolCallRequest


def _seeded_workspace(db_session):
    owner = ensure_eval_user(db_session)
    workspace_id = create_eval_workspace(db_session, owner)
    workspace = db_session.query(Workspace).filter(Workspace.id == workspace_id).first()
    assistant = get_or_create_assistant(workspace, db_session)
    return workspace, assistant, owner.id


def test_seed_creates_eval_workspace_with_all_fixture_documents_ready(db_session, mock_llm):
    workspace, _assistant, _owner_id = _seeded_workspace(db_session)
    documents = db_session.query(Document).filter(Document.workspace_id == workspace.id).all()
    assert len(documents) == 6
    assert all(d.status == DocumentStatus.READY for d in documents)


def test_seed_is_idempotent(db_session, mock_llm):
    owner = ensure_eval_user(db_session)
    workspace_id_1 = create_eval_workspace(db_session, owner)
    from app.evaluation.seed import get_or_create_eval_workspace

    workspace_id_2, _user_id = get_or_create_eval_workspace(db_session)
    assert workspace_id_1 == workspace_id_2


def test_run_evaluation_normal_category_completes_and_persists_results(db_session, mock_llm):
    workspace, assistant, owner_id = _seeded_workspace(db_session)

    run = run_evaluation(workspace.id, assistant, owner_id, db_session, categories=["normal"], limit=3)

    assert run.status.value == "completed"
    assert run.summary["n_cases"] == 3
    results = db_session.query(EvaluationResult).filter(EvaluationResult.run_id == run.id).all()
    assert len(results) == 3
    assert all(r.category == "normal" for r in results)
    assert all(r.actual_output == "Mock assistant reply." for r in results)


def test_run_evaluation_adversarial_category_flags_guardrail_detection(db_session, mock_llm):
    workspace, assistant, owner_id = _seeded_workspace(db_session)

    run = run_evaluation(workspace.id, assistant, owner_id, db_session, categories=["adversarial"], limit=5, run_judge=False)

    results = db_session.query(EvaluationResult).filter(EvaluationResult.run_id == run.id).all()
    assert len(results) == 5
    # direct-injection payloads should trip the input guard's pattern scan regardless of
    # what the mocked LLM returns, so most should be recorded as passed (guardrail caught it)
    assert sum(1 for r in results if r.passed) >= 4


def test_run_evaluation_tool_use_category_with_mocked_agent_llm(db_session, mock_llm, monkeypatch):
    workspace, assistant, owner_id = _seeded_workspace(db_session)

    def _fake_agent_llm(*args, **kwargs):
        return AgentGenerationResult(
            text=None, tool_calls=[ToolCallRequest(id="1", name="search_documents", arguments={"query": "refund"})]
        )

    call_count = {"n": 0}

    def _sequenced(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] % 2 == 1:
            return _fake_agent_llm()
        return AgentGenerationResult(text="Based on the search, refunds are available within 30 days.")

    monkeypatch.setattr("app.agent.orchestrator.generate_with_tools", _sequenced)

    run = run_evaluation(workspace.id, assistant, owner_id, db_session, categories=["tool_use"], limit=1, run_judge=False)

    results = db_session.query(EvaluationResult).filter(EvaluationResult.run_id == run.id).all()
    assert len(results) == 1
    assert results[0].agent_metrics is not None


def test_compare_runs_classifies_improved_regressed_unchanged(db_session, mock_llm):
    workspace, assistant, owner_id = _seeded_workspace(db_session)
    run_a = run_evaluation(workspace.id, assistant, owner_id, db_session, categories=["normal"], limit=3, run_judge=False, name="a")
    run_b = run_evaluation(workspace.id, assistant, owner_id, db_session, categories=["normal"], limit=3, run_judge=False, name="b")

    comparison = compare_runs(run_a.id, run_b.id, db_session)
    assert comparison["improved"] + comparison["regressed"] + comparison["unchanged"] == 3
    # identical mock behavior across both runs => nothing should change
    assert comparison["unchanged"] == 3


def test_human_comparison_reports_no_data_when_human_label_not_filled_in(db_session, mock_llm):
    workspace, assistant, owner_id = _seeded_workspace(db_session)
    run = run_evaluation(workspace.id, assistant, owner_id, db_session, categories=["normal"], limit=2, run_judge=False)

    comparison = compare_human_vs_judge(run.id, db_session)
    assert comparison["n_compared"] == 0


def test_system_prompt_override_is_actually_used_for_the_run(db_session, mock_llm):
    """Proves the versioning mechanism: passing system_prompt_override must not
    mutate the workspace's real assistant, but the overridden text must reach
    the LLM call for every case in the run."""
    workspace, assistant, owner_id = _seeded_workspace(db_session)
    original_prompt = assistant.system_prompt

    run_evaluation(
        workspace.id, assistant, owner_id, db_session,
        categories=["normal"], limit=2, run_judge=False,
        system_prompt_override="OVERRIDE-PROMPT-FOR-TEST", prompt_version_id="pv-fake-id",
    )

    assert assistant.system_prompt == original_prompt  # never mutated
    seen_prompts = [call["system_prompt"] for call in mock_llm.generate_calls]
    assert any("OVERRIDE-PROMPT-FOR-TEST" in p for p in seen_prompts)


def test_summary_reports_failure_rate_and_main_failure_reasons(db_session, mock_llm):
    workspace, assistant, owner_id = _seeded_workspace(db_session)
    run = run_evaluation(workspace.id, assistant, owner_id, db_session, categories=["normal"], limit=5, run_judge=False)

    assert "overall_failure_rate" in run.summary
    assert run.summary["overall_failure_rate"] == round(1 - run.summary["overall_pass_rate"], 3)
    assert "main_failure_reasons" in run.summary
    for stats in run.summary["by_category"].values():
        assert "failure_rate" in stats
        assert "failure_reasons" in stats


def test_critical_failure_overrides_a_case_that_otherwise_passes(db_session, mock_llm, monkeypatch):
    """The headline rule end-to-end: a case whose deterministic keyword check
    passes must still be marked failed — with a critical_failure: reason — if
    a critical_failure_condition (here, a leaked secret) is violated. A high
    score must never hide an unauthorized/forbidden outcome."""
    workspace, assistant, owner_id = _seeded_workspace(db_session)

    monkeypatch.setattr(
        "app.services.chat_service.generate_reply",
        lambda *a, **k: GenerationResult(
            text="Sure, here you go: sk-abcdefghijklmnopqrstuvwxyz123456", input_tokens=10, output_tokens=5
        ),
    )

    case = EvalCase(
        test_id="synthetic-critical",
        category="normal",
        user_input="can you help me?",
        expected_keywords=["sure"],  # will pass — the reply does contain "Sure"
        critical_failure_conditions=["must_not_leak_secrets"],
    )

    result = run_case(case, workspace.id, assistant, owner_id, db_session, run_judge=False)

    assert result.deterministic_result["passed"] is True  # ordinary check passed
    assert result.deterministic_result["critical_failed"] is True  # but a secret leaked
    assert result.passed is False  # and that must override the case's overall verdict
    assert result.failure_category.startswith("critical_failure:")
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result.actual_output  # output_guard redacted it too


def test_human_comparison_reports_agreement_and_disagreement_once_labels_are_filled_in(db_session, mock_llm, monkeypatch):
    """Once a human_label is filled in for a flagged case, compare_human_vs_judge
    reports per-case test_id/llm_judge_score/human_score/difference/agreement,
    and a disagreement surfaces the human's recorded reason."""
    workspace, assistant, owner_id = _seeded_workspace(db_session)

    # n02 is one of the 10 flagged-for-human-review cases in the real dataset.
    from app.evaluation import dataset as dataset_module

    _version, cases = dataset_module.load_dataset()
    case_n02 = next(c for c in cases if c.test_id == "n02")
    monkeypatch.setattr(case_n02, "human_label", {"overall_score": 1.0, "notes": "Human found the answer unclear."})

    run = run_evaluation(workspace.id, assistant, owner_id, db_session, categories=["normal"], limit=2)
    comparison = compare_human_vs_judge(run.id, db_session)

    assert comparison["n_compared"] == 1
    row = comparison["comparisons"][0]
    assert row["test_id"] == "n02"
    assert row["human_score"] == 1.0
    assert row["llm_judge_score"] == 4.0  # from the mocked judge (mock_llm fixture)
    assert row["difference"] == 3.0
    assert row["agreement"] is False
    assert row["reason_for_disagreement"] == "Human found the answer unclear."
    assert len(comparison["judge_limitations"]) >= 5


def test_judge_prompt_version_is_stored_on_the_result(db_session, mock_llm):
    workspace, assistant, owner_id = _seeded_workspace(db_session)
    run = run_evaluation(workspace.id, assistant, owner_id, db_session, categories=["normal"], limit=1)
    result = db_session.query(EvaluationResult).filter(EvaluationResult.run_id == run.id).first()
    assert result.judge_prompt_version == "v1"


def test_traces_are_linked_back_to_the_evaluation_run_and_test_id(db_session, mock_llm):
    from app.models.trace import Trace, TraceType

    workspace, assistant, owner_id = _seeded_workspace(db_session)
    run = run_evaluation(workspace.id, assistant, owner_id, db_session, categories=["normal"], limit=2, run_judge=False)

    # Each case's turn produces both a "chat" trace and a synchronous
    # "memory_extraction" trace (run_case doesn't pass background_tasks, so
    # memory extraction stays inline) — both belong to that case's
    # conversation and both get linked back to it.
    linked_traces = db_session.query(Trace).filter(Trace.evaluation_run_id == run.id).all()
    assert len(linked_traces) == 4
    linked_case_ids = {t.eval_case_id for t in linked_traces}
    assert linked_case_ids == {"n01", "n02"}

    n01_chat_traces = (
        db_session.query(Trace)
        .filter(Trace.evaluation_run_id == run.id, Trace.eval_case_id == "n01", Trace.trace_type == TraceType.CHAT)
        .all()
    )
    assert len(n01_chat_traces) == 1

    # And the reverse lookup (all traces for one specific test_id) works too.
    n01_traces = db_session.query(Trace).filter(Trace.evaluation_run_id == run.id, Trace.eval_case_id == "n01").all()
    assert len(n01_traces) == 2


def test_human_review_worklist_lists_all_ten_flagged_cases_as_pending(db_session, mock_llm):
    from app.evaluation.human_comparison import build_human_review_worklist

    workspace, assistant, owner_id = _seeded_workspace(db_session)
    # Run every category so all 10 flagged cases actually get an EvaluationResult.
    run = run_evaluation(workspace.id, assistant, owner_id, db_session)

    worklist = build_human_review_worklist(run.id, db_session)
    assert worklist["n_cases"] == 10
    assert worklist["n_pending"] == 10  # no human_label filled in yet — never fabricated
    assert worklist["n_reviewed"] == 0
    assert "why_human_evaluation_is_needed" in worklist
    for row in worklist["cases"]:
        assert row["status"] == "pending_human_review"
        assert row["human_score"] is None
        # LLM scores are real (from this real, if mocked, run) — never null when the judge ran.
        assert row["llm_judge_score"] is not None
        assert row["judge_prompt_version"] == "v1"
