"""Loads the checked-in evaluation dataset (app/evaluation/data/eval_dataset.json)
— kept as a reviewable JSON file rather than DB rows so it can be read and
diffed like any other test fixture. Only *run results* are persisted to the
database (see models/evaluation.py) — this module holds test *definitions*
only, deliberately kept free of any execution/result fields (actual_result,
score, pass_fail are result-side concepts; see evaluation/runner.py and
evaluation/reporting.py for how the two are joined for reporting).
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_DATASET_PATH = Path(__file__).parent / "data" / "eval_dataset.json"
FIXTURE_DOCUMENTS_DIR = Path(__file__).parent / "data" / "fixture_documents"

REQUIRED_CATEGORIES = {
    "normal": 15,
    "difficult": 10,
    "ambiguous": 8,
    "tool_use": 10,
    "rag": 10,
    "adversarial": 7,
}


@dataclass
class EvalCase:
    # --- required fields (per the Week 6 evaluation-foundation spec) ---
    test_id: str
    category: str
    user_input: str
    expected_behavior: str | None = None
    expected_tool: str | None = None
    expected_source: str | None = None
    expected_structured_output: dict | None = None
    approval_required: bool = False
    critical_failure_conditions: list[str] = field(default_factory=list)
    notes: str | None = None

    # --- supporting fields used by the deterministic evaluators/metrics modules ---
    difficulty: str = "medium"
    tags: list[str] = field(default_factory=list)
    expected_output: str | None = None
    expected_keywords: list[str] = field(default_factory=list)
    expected_args: dict | None = None
    expected_risk_level: str | None = None
    adversarial_type: str | None = None
    flagged_for_human_review: bool = False
    human_label: dict | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> "EvalCase":
        known_fields = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known_fields})


@lru_cache
def load_dataset() -> tuple[str, list[EvalCase]]:
    raw = json.loads(_DATASET_PATH.read_text(encoding="utf-8"))
    cases = [EvalCase.from_dict(case) for case in raw["cases"]]
    return raw["dataset_version"], cases


def load_cases(category: str | None = None) -> list[EvalCase]:
    _version, cases = load_dataset()
    if category is None:
        return cases
    return [c for c in cases if c.category == category]


def get_case(test_id: str) -> EvalCase | None:
    _version, cases = load_dataset()
    return next((c for c in cases if c.test_id == test_id), None)


def validate_dataset() -> dict:
    """Structural validation of the checked-in dataset: unique ids, every
    required field present, and every category at or above its required
    minimum count. Returns a report dict rather than raising, so it can be
    surfaced (CLI, tests, docs) without special-casing failure handling."""
    _version, cases = load_dataset()

    errors: list[str] = []

    ids = [c.test_id for c in cases]
    duplicate_ids = [test_id for test_id, count in Counter(ids).items() if count > 1]
    if duplicate_ids:
        errors.append(f"Duplicate test_id(s): {duplicate_ids}")

    for case in cases:
        if not case.test_id:
            errors.append("A case is missing test_id")
        if not case.category:
            errors.append(f"{case.test_id}: missing category")
        if not case.user_input:
            errors.append(f"{case.test_id}: missing user_input")
        if case.category not in REQUIRED_CATEGORIES:
            errors.append(f"{case.test_id}: unknown category '{case.category}'")

    category_counts = dict(Counter(c.category for c in cases))
    for category, minimum in REQUIRED_CATEGORIES.items():
        actual = category_counts.get(category, 0)
        if actual < minimum:
            errors.append(f"Category '{category}' has {actual} cases, needs >= {minimum}")

    return {
        "valid": len(errors) == 0,
        "total_cases": len(cases),
        "unique_test_ids": len(set(ids)) == len(ids),
        "category_counts": category_counts,
        "category_minimums": REQUIRED_CATEGORIES,
        "errors": errors,
    }
