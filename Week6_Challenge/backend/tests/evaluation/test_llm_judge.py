from app.evaluation.llm_judge import JudgeScore, judge_reply
from app.services.llm_service import GenerationResult, LLMError


def test_judge_reply_parses_valid_json_response(monkeypatch):
    monkeypatch.setattr(
        "app.evaluation.llm_judge.generate_reply",
        lambda *a, **k: GenerationResult(
            text=(
                '{"correctness": 5, "relevance": 4, "completeness": 5, "clarity": 4, '
                '"groundedness": 5, "explanation": "Accurate, relevant, and grounded."}'
            )
        ),
    )
    result = judge_reply("What is the refund window?", "30 days.", "Refunds within 30 days.")
    assert result["overall_score"] == 4.6
    assert result["error"] is None
    assert result["explanation"] == "Accurate, relevant, and grounded."
    assert result["correctness"] == 5
    assert result["relevance"] == 4


def test_judge_reply_strips_markdown_code_fence(monkeypatch):
    monkeypatch.setattr(
        "app.evaluation.llm_judge.generate_reply",
        lambda *a, **k: GenerationResult(
            text=(
                '```json\n{"correctness": 3, "relevance": 3, "completeness": 3, "clarity": 3, '
                '"groundedness": 3, "explanation": "ok"}\n```'
            )
        ),
    )
    result = judge_reply("x", "y")
    assert result["overall_score"] == 3.0


def test_judge_reply_falls_back_to_null_score_on_llm_error(monkeypatch):
    def _raise(*a, **k):
        raise LLMError("no api key")

    monkeypatch.setattr("app.evaluation.llm_judge.generate_reply", _raise)
    result = judge_reply("x", "y")
    assert result["overall_score"] is None
    assert result["error"] is not None


def test_judge_reply_falls_back_to_null_score_on_bad_json(monkeypatch):
    monkeypatch.setattr(
        "app.evaluation.llm_judge.generate_reply", lambda *a, **k: GenerationResult(text="not json at all")
    )
    result = judge_reply("x", "y")
    assert result["overall_score"] is None


def test_judge_reply_falls_back_when_json_is_valid_but_violates_the_schema(monkeypatch):
    """A score out of the 1-5 range (or a missing dimension) must be rejected
    by schema validation, not silently coerced or accepted."""
    monkeypatch.setattr(
        "app.evaluation.llm_judge.generate_reply",
        lambda *a, **k: GenerationResult(text='{"correctness": 99, "relevance": 4, "completeness": 4, "clarity": 4, "groundedness": 4, "explanation": "bad"}'),
    )
    result = judge_reply("x", "y")
    assert result["overall_score"] is None
    assert result["error"] is not None


def test_judge_reply_falls_back_when_a_required_dimension_is_missing(monkeypatch):
    monkeypatch.setattr(
        "app.evaluation.llm_judge.generate_reply",
        lambda *a, **k: GenerationResult(text='{"correctness": 4, "relevance": 4, "explanation": "incomplete"}'),
    )
    result = judge_reply("x", "y")
    assert result["overall_score"] is None


def test_judge_reply_includes_expected_behavior_in_the_prompt_when_given(monkeypatch):
    captured = {}

    def _fake(system_prompt, history, **kwargs):
        captured["content"] = history[0]["content"]
        return GenerationResult(
            text='{"correctness": 4, "relevance": 4, "completeness": 4, "clarity": 4, "groundedness": 4, "explanation": "ok"}'
        )

    monkeypatch.setattr("app.evaluation.llm_judge.generate_reply", _fake)
    judge_reply("Can you fix it?", "Which thing would you like me to fix?", expected_behavior="ask_for_clarification")
    assert "ask_for_clarification" in captured["content"]


def test_judge_score_overall_is_the_mean_of_all_five_dimensions():
    score = JudgeScore(correctness=5, relevance=5, completeness=5, clarity=5, groundedness=5, explanation="x")
    assert score.overall_score == 5.0
    score = JudgeScore(correctness=1, relevance=2, completeness=3, clarity=4, groundedness=5, explanation="x")
    assert score.overall_score == 3.0
