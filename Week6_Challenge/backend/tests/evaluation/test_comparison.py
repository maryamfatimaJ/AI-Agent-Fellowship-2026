"""Directly proves compare_runs() can detect all three outcomes — improved,
regressed, and unchanged — including the specific requirement that a new
prompt/model version making an existing case WORSE must be detected, not
just improvements. Constructs EvaluationResult rows directly (rather than
running the full chat pipeline) so the classification logic itself is
tested in isolation from model/judge behavior."""

from app.evaluation.comparison import compare_runs
from app.models.evaluation import EvaluationResult, EvaluationRun, EvaluationRunStatus


def _make_run(db_session, workspace_id: str, name: str) -> EvaluationRun:
    run = EvaluationRun(
        workspace_id=workspace_id, name=name, dataset_version="test", provider="gemini", model="test-model",
        status=EvaluationRunStatus.COMPLETED,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def _make_result(db_session, run_id: str, case_id: str, *, passed: bool, judge_score: float | None) -> None:
    db_session.add(
        EvaluationResult(
            run_id=run_id, case_id=case_id, category="normal", actual_output="x", passed=passed, judge_score=judge_score,
        )
    )
    db_session.commit()


def test_compare_runs_detects_a_case_that_regressed(db_session):
    run_a = _make_run(db_session, "ws-1", "before")
    run_b = _make_run(db_session, "ws-1", "after")

    # n01 passed in run A but fails in run B — the new version made it worse.
    _make_result(db_session, run_a.id, "n01", passed=True, judge_score=4.5)
    _make_result(db_session, run_b.id, "n01", passed=False, judge_score=2.0)

    result = compare_runs(run_a.id, run_b.id, db_session)

    assert result["regressed"] == 1
    assert result["improved"] == 0
    assert result["cases"][0]["status"] == "regressed"
    assert result["cases"][0]["run_a_passed"] is True
    assert result["cases"][0]["run_b_passed"] is False


def test_compare_runs_detects_a_case_that_improved(db_session):
    run_a = _make_run(db_session, "ws-1", "before")
    run_b = _make_run(db_session, "ws-1", "after")

    _make_result(db_session, run_a.id, "n02", passed=False, judge_score=1.5)
    _make_result(db_session, run_b.id, "n02", passed=True, judge_score=4.0)

    result = compare_runs(run_a.id, run_b.id, db_session)

    assert result["improved"] == 1
    assert result["regressed"] == 0


def test_compare_runs_detects_a_judge_score_regression_even_when_pass_fail_is_unchanged(db_session):
    """A case can stay 'passed' in both runs but still get meaningfully worse
    by the judge's own scoring — this must not be silently reported as
    unchanged just because the pass/fail bit didn't flip."""
    run_a = _make_run(db_session, "ws-1", "before")
    run_b = _make_run(db_session, "ws-1", "after")

    _make_result(db_session, run_a.id, "n03", passed=True, judge_score=4.8)
    _make_result(db_session, run_b.id, "n03", passed=True, judge_score=3.5)  # still passes, but notably worse

    result = compare_runs(run_a.id, run_b.id, db_session)

    assert result["regressed"] == 1
    assert result["cases"][0]["status"] == "regressed"


def test_compare_runs_reports_unchanged_when_nothing_moved(db_session):
    run_a = _make_run(db_session, "ws-1", "before")
    run_b = _make_run(db_session, "ws-1", "after")

    _make_result(db_session, run_a.id, "n04", passed=True, judge_score=4.0)
    _make_result(db_session, run_b.id, "n04", passed=True, judge_score=4.1)  # within tolerance

    result = compare_runs(run_a.id, run_b.id, db_session)

    assert result["unchanged"] == 1
    assert result["improved"] == 0
    assert result["regressed"] == 0


def test_compare_runs_only_compares_cases_present_in_both_runs(db_session):
    run_a = _make_run(db_session, "ws-1", "before")
    run_b = _make_run(db_session, "ws-1", "after")

    _make_result(db_session, run_a.id, "n05", passed=True, judge_score=4.0)
    _make_result(db_session, run_b.id, "n06", passed=True, judge_score=4.0)  # different case id

    result = compare_runs(run_a.id, run_b.id, db_session)

    assert result["improved"] + result["regressed"] + result["unchanged"] == 0
    assert result["cases"] == []
