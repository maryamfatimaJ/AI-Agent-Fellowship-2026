"""Diffs two evaluation runs (same dataset) case by case — used both for
prompt-version comparison (3 versions x same dataset) and model comparison
(2+ providers/models x same dataset). A case is "improved" if it now passes
and didn't before (or its judge score rose by more than a small tolerance),
"regressed" for the opposite, "unchanged" otherwise.
"""

from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationResult

_JUDGE_SCORE_TOLERANCE = 0.25


def _classify(run_a_passed: bool, run_b_passed: bool, score_a: float | None, score_b: float | None) -> str:
    if run_a_passed != run_b_passed:
        return "improved" if run_b_passed else "regressed"
    if score_a is not None and score_b is not None:
        delta = score_b - score_a
        if delta > _JUDGE_SCORE_TOLERANCE:
            return "improved"
        if delta < -_JUDGE_SCORE_TOLERANCE:
            return "regressed"
    return "unchanged"


def compare_runs(run_a_id: str, run_b_id: str, db: Session) -> dict:
    results_a = {r.case_id: r for r in db.query(EvaluationResult).filter(EvaluationResult.run_id == run_a_id)}
    results_b = {r.case_id: r for r in db.query(EvaluationResult).filter(EvaluationResult.run_id == run_b_id)}

    shared_case_ids = sorted(set(results_a) & set(results_b))
    cases = []
    counts = {"improved": 0, "regressed": 0, "unchanged": 0}

    for case_id in shared_case_ids:
        a, b = results_a[case_id], results_b[case_id]
        status = _classify(a.passed, b.passed, a.judge_score, b.judge_score)
        counts[status] += 1
        cases.append(
            {
                "case_id": case_id,
                "category": a.category,
                "status": status,
                "run_a_passed": a.passed,
                "run_b_passed": b.passed,
                "run_a_judge_score": a.judge_score,
                "run_b_judge_score": b.judge_score,
            }
        )

    return {
        "run_a_id": run_a_id,
        "run_b_id": run_b_id,
        "improved": counts["improved"],
        "regressed": counts["regressed"],
        "unchanged": counts["unchanged"],
        "cases": cases,
    }
