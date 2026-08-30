from datetime import datetime

from pydantic import BaseModel

from app.models.evaluation import EvaluationRunStatus


class RunEvaluationRequest(BaseModel):
    name: str = "evaluation run"
    provider: str | None = None
    model: str | None = None
    prompt_version_id: str | None = None
    categories: list[str] | None = None
    limit: int | None = None
    run_judge: bool = True


class EvaluationResultRead(BaseModel):
    id: str
    case_id: str
    category: str
    actual_output: str | None
    deterministic_result: dict | None
    judge_score: float | None
    judge_reasoning: str | None
    judge_prompt_version: str | None
    rag_metrics: dict | None
    agent_metrics: dict | None
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    passed: bool
    failure_category: str | None

    model_config = {"from_attributes": True}


class EvaluationRunRead(BaseModel):
    id: str
    name: str
    dataset_version: str
    prompt_version_id: str | None
    provider: str
    model: str
    status: EvaluationRunStatus
    summary: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationRunDetailRead(EvaluationRunRead):
    results: list[EvaluationResultRead]


class EvaluationRunListRead(BaseModel):
    items: list[EvaluationRunRead]
    total: int


class ComparisonCaseDiff(BaseModel):
    case_id: str
    category: str
    status: str  # "improved" | "regressed" | "unchanged"
    run_a_passed: bool
    run_b_passed: bool
    run_a_judge_score: float | None
    run_b_judge_score: float | None


class ComparisonResult(BaseModel):
    run_a_id: str
    run_b_id: str
    improved: int
    regressed: int
    unchanged: int
    cases: list[ComparisonCaseDiff]
