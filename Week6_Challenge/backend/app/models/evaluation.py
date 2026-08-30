import enum

from sqlalchemy import Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, generate_uuid


class EvaluationRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvaluationRun(Base, TimestampMixin):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("prompt_versions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[EvaluationRunStatus] = mapped_column(
        Enum(EvaluationRunStatus), default=EvaluationRunStatus.RUNNING, nullable=False
    )
    started_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    results: Mapped[list["EvaluationResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class EvaluationResult(Base, TimestampMixin):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    case_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actual_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    deterministic_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judge_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which version of the judge PROMPT produced judge_score/judge_reasoning —
    # distinct from prompt_version_id above (the run's *assistant* system
    # prompt). Tracked so a future change to the judge prompt itself can be
    # compared/regression-tested independently of assistant-prompt changes;
    # see app/evaluation/llm_judge.py::JUDGE_PROMPT_VERSION.
    judge_prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rag_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agent_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    run: Mapped["EvaluationRun"] = relationship(back_populates="results")
