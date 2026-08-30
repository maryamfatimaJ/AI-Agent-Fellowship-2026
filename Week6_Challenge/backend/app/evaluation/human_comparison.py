"""Compares the LLM judge's score against a human-provided score for the 10
cases flagged in eval_dataset.json (flagged_for_human_review=true). Human
scores live in that same JSON file's human_label field — a reviewer reads the
actual model output from a completed run (via build_human_review_worklist()
below, or the evaluations API) and fills in
{"overall_score": 1-5, "notes": "...", "evaluation_date": "YYYY-MM-DD"} for
each flagged case, then compare_human_vs_judge() reports per-case
agreement/disagreement plus an aggregate — never a claim that the judge is a
reliable substitute for human judgment (see JUDGE_LIMITATIONS, documented in
docs/evaluation/evaluation-foundation.md).

WHY_HUMAN_EVALUATION_IS_NEEDED: an LLM judge's score is cheap and fast but
carries the exact biases listed in JUDGE_LIMITATIONS below — none of which a
second LLM call can self-detect. Comparing it against real human judgment on
a representative sample is the only way to know whether the judge's scores
are actually trustworthy for this application's specific tasks, or whether
they're systematically off in a way that would quietly mislead every later
decision (prompt changes, model choice) built on top of them.
"""

from sqlalchemy.orm import Session

from app.evaluation.dataset import load_dataset
from app.models.evaluation import EvaluationResult

WHY_HUMAN_EVALUATION_IS_NEEDED = (
    "An LLM judge's score is cheap and fast but carries real, undetectable-by-itself "
    "biases (see JUDGE_LIMITATIONS). Comparing it against real human judgment on a "
    "representative sample is the only way to know whether the judge's scores are "
    "actually trustworthy for this application's specific tasks, rather than "
    "systematically off in a way that quietly misleads every later decision "
    "(prompt changes, model choice) built on top of them."
)

# A case counts as "agreement" when the two scores are within 1 point on the
# 1-5 scale — a stricter exact-match threshold would flag near-identical
# scores (e.g. 4 vs 4.2) as disagreement, which isn't a meaningful signal.
AGREEMENT_THRESHOLD = 1.0

JUDGE_LIMITATIONS = [
    "model_bias: the judge is itself an LLM and inherits that model's own blind spots "
    "and preferences — it is not a neutral, external ground truth.",
    "position_bias: LLM judges are documented to weight earlier or later content in a "
    "prompt inconsistently; this implementation doesn't test for or correct that.",
    "verbosity_bias: LLM judges tend to rate longer, more elaborate answers higher even "
    "when a shorter answer is equally or more correct.",
    "self_preference: a judge model may rate replies from its own model family more "
    "favorably than replies from a different provider — relevant here since the judge "
    "and the assistant can be the same underlying model.",
    "inconsistent_scoring: temperature=0 improves repeatability but does not guarantee "
    "an identical score for the same input on every call; provider-side nondeterminism "
    "still exists.",
    "prompt_sensitivity: small changes to the judge prompt's wording can shift scores "
    "measurably — the scores here are only comparable to each other under this exact "
    "judge prompt, not to scores from a differently-worded judge.",
]


def compare_human_vs_judge(run_id: str, db: Session) -> dict:
    _version, cases = load_dataset()
    flagged = {c.test_id: c for c in cases if c.flagged_for_human_review}
    if not flagged:
        return {"n_flagged": 0, "n_compared": 0, "judge_limitations": JUDGE_LIMITATIONS}

    results = (
        db.query(EvaluationResult)
        .filter(EvaluationResult.run_id == run_id, EvaluationResult.case_id.in_(flagged.keys()))
        .all()
    )

    comparisons = []
    for result in results:
        case = flagged[result.case_id]
        human_label = case.human_label or {}
        human_score = human_label.get("overall_score")
        if human_score is None or result.judge_score is None:
            continue
        difference = round(abs(human_score - result.judge_score), 3)
        agrees = difference <= AGREEMENT_THRESHOLD
        comparisons.append(
            {
                "test_id": result.case_id,
                "llm_judge_score": result.judge_score,
                "human_score": human_score,
                "difference": difference,
                "agreement": agrees,
                "reason_for_disagreement": None if agrees else human_label.get("notes"),
                "human_notes": human_label.get("notes"),
                "evaluation_date": human_label.get("evaluation_date"),
            }
        )

    if not comparisons:
        return {
            "n_flagged": len(flagged),
            "n_compared": 0,
            "note": "No human_label filled in yet for the flagged cases — see eval_dataset.json",
            "judge_limitations": JUDGE_LIMITATIONS,
        }

    diffs = [c["difference"] for c in comparisons]
    agreements = [c["agreement"] for c in comparisons]
    return {
        "n_flagged": len(flagged),
        "n_compared": len(comparisons),
        "mean_absolute_difference": round(sum(diffs) / len(diffs), 3),
        "agreement_rate": round(sum(1 for a in agreements if a) / len(agreements), 3),
        "comparisons": comparisons,
        "judge_limitations": JUDGE_LIMITATIONS,
    }


def build_human_review_worklist(run_id: str, db: Session) -> dict:
    """The structured human-review workflow itself: for each of the 10
    flagged cases, pulls the REAL LLM judge score/explanation from a
    completed evaluation run and pairs it with whatever human fields exist
    so far (None/"pending" if a human hasn't reviewed it yet). Never invents
    a human score — `status` is exactly "pending_human_review" until
    eval_dataset.json's human_label is filled in for that case.

    Intended consumption: GET .../evaluations/{run_id}/human-review-worklist
    (see api/routers/evaluations.py) or
    scripts/generate_human_review_worklist.py, either of which a reviewer can
    read, then hand-edit eval_dataset.json's human_label fields directly."""
    _version, cases = load_dataset()
    flagged = {c.test_id: c for c in cases if c.flagged_for_human_review}

    results = {
        r.case_id: r
        for r in db.query(EvaluationResult).filter(
            EvaluationResult.run_id == run_id, EvaluationResult.case_id.in_(flagged.keys())
        )
    }

    worklist = []
    for test_id, case in flagged.items():
        result = results.get(test_id)
        human_label = case.human_label or {}
        human_score = human_label.get("overall_score")
        worklist.append(
            {
                "test_id": test_id,
                "category": case.category,
                "user_input": case.user_input,
                "expected_behavior": case.expected_behavior,
                "actual_output": (result.actual_output[:500] if result and result.actual_output else None),
                "llm_judge_score": result.judge_score if result else None,
                "llm_explanation": result.judge_reasoning if result else None,
                "judge_prompt_version": result.judge_prompt_version if result else None,
                "human_score": human_score,
                "human_notes": human_label.get("notes"),
                "evaluation_date": human_label.get("evaluation_date"),
                "status": "reviewed" if human_score is not None else "pending_human_review",
            }
        )

    return {
        "run_id": run_id,
        "n_cases": len(worklist),
        "n_reviewed": sum(1 for row in worklist if row["status"] == "reviewed"),
        "n_pending": sum(1 for row in worklist if row["status"] == "pending_human_review"),
        "why_human_evaluation_is_needed": WHY_HUMAN_EVALUATION_IS_NEEDED,
        "cases": worklist,
    }
