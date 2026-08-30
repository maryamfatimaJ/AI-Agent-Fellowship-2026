from app.evaluation.dataset import REQUIRED_CATEGORIES, get_case, load_cases, load_dataset, validate_dataset


def test_dataset_loads_with_expected_shape():
    version, cases = load_dataset()
    assert version == "v1"
    assert len(cases) >= 60

    categories = {c.category for c in cases}
    assert categories == {"normal", "difficult", "ambiguous", "tool_use", "rag", "adversarial"}


def test_dataset_meets_every_category_minimum():
    _version, cases = load_dataset()
    counts: dict[str, int] = {}
    for case in cases:
        counts[case.category] = counts.get(case.category, 0) + 1
    for category, minimum in REQUIRED_CATEGORIES.items():
        assert counts.get(category, 0) >= minimum, f"{category}: {counts.get(category, 0)} < {minimum}"


def test_dataset_total_is_in_the_65_to_70_range():
    _version, cases = load_dataset()
    assert 65 <= len(cases) <= 70


def test_ten_cases_are_flagged_for_human_review():
    _version, cases = load_dataset()
    flagged = [c for c in cases if c.flagged_for_human_review]
    assert len(flagged) == 10


def test_all_test_ids_are_unique():
    _version, cases = load_dataset()
    ids = [c.test_id for c in cases]
    assert len(ids) == len(set(ids))


def test_every_case_has_the_required_fields_populated():
    _version, cases = load_dataset()
    for case in cases:
        assert case.test_id, case
        assert case.category, case
        assert case.user_input, case
        # expected_behavior, expected_tool, expected_source, expected_structured_output,
        # and critical_failure_conditions are legitimately None/empty for many cases —
        # only test_id/category/user_input are universally required.


def test_get_case_returns_the_matching_case():
    case = get_case("n01")
    assert case is not None
    assert case.category == "normal"


def test_get_case_returns_none_for_unknown_id():
    assert get_case("does-not-exist") is None


def test_tool_use_cases_all_declare_an_expected_tool():
    for case in load_cases("tool_use"):
        assert case.expected_tool is not None, case.test_id


def test_rag_cases_all_declare_an_expected_source():
    for case in load_cases("rag"):
        assert case.expected_source is not None, case.test_id


def test_adversarial_cases_declare_an_adversarial_type_and_critical_condition():
    for case in load_cases("adversarial"):
        assert case.adversarial_type is not None, case.test_id
        assert len(case.critical_failure_conditions) > 0, case.test_id


def test_high_risk_tool_case_requires_approval():
    case = get_case("t07")
    assert case is not None
    assert case.approval_required is True
    assert "must_not_execute_without_approval" in case.critical_failure_conditions


# --- validate_dataset() --------------------------------------------------------


def test_validate_dataset_reports_valid_for_the_shipped_dataset():
    report = validate_dataset()
    assert report["valid"] is True
    assert report["errors"] == []
    assert report["unique_test_ids"] is True
    assert report["total_cases"] == len(load_cases())


def test_validate_dataset_reports_category_counts_and_minimums():
    report = validate_dataset()
    for category, minimum in REQUIRED_CATEGORIES.items():
        assert report["category_counts"][category] >= minimum
