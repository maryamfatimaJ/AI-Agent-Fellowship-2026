"""The strongly-typed LangGraph state for a research run.

Design notes
------------
Fields fall into two groups:

1. **Sequential / single-writer fields** — written by exactly one node at a
   time (e.g. `research_objective` by request_analysis_node). These use plain
   TypedDict entries; LangGraph's default behavior (overwrite) is correct.

2. **Concurrent / accumulating fields** — written by many parallel branches
   in the same superstep (e.g. `evidence` written by every fanned-out
   research_node instance) or that must retain full history across
   sequential supersteps (e.g. `critic_feedback` across revision rounds).
   These are `Annotated[..., operator.add]` (or a custom reducer) so
   LangGraph concatenates rather than overwrites.

Only primitive / Pydantic-model values are stored (never raw LLM
chain-of-thought), matching the "never store chain of thought" execution
trace requirement.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.schemas.analysis import AnalysisResult, BonusInsight
from app.schemas.critic import CriticFeedback
from app.schemas.evidence import EvidenceItem
from app.schemas.execution import ExecutionLogEntry, WorkflowError
from app.schemas.report import FinalReport
from app.schemas.request import ClarificationExchange
from app.schemas.task import ResearchTask
from app.state.reducers import merge_unique_str


class ResearchState(TypedDict, total=False):
    # --- identity -------------------------------------------------------
    run_id: str
    user_request: str
    deliverable_hint: str | None
    started_at: str
    updated_at: str

    # --- clarification --------------------------------------------------
    clarifications: Annotated[list[ClarificationExchange], operator.add]
    clarification_round: int
    needs_clarification: bool
    pending_clarification_question: str | None

    # --- request analysis -------------------------------------------------
    research_objective: str
    research_questions: list[str]
    deliverable: str
    constraints: list[str]
    comparison_criteria: list[str]
    time_horizon: str | None
    missing_information: list[str]
    entities: list[str]

    # --- planning -----------------------------------------------------------
    task_plan: list[ResearchTask]
    task_plan_rationale: str
    current_task: ResearchTask | None
    active_tasks: Annotated[list[str], operator.add]
    completed_tasks: Annotated[list[str], merge_unique_str]

    # --- workflow bookkeeping ------------------------------------------------
    workflow_status: str

    # --- research / evidence --------------------------------------------------
    evidence: Annotated[list[EvidenceItem], operator.add]

    # --- analysis --------------------------------------------------------------
    analysis: AnalysisResult | None
    bonus_insights: Annotated[list[BonusInsight], operator.add]

    # --- critic / revision loop --------------------------------------------------
    critic_feedback: Annotated[list[CriticFeedback], operator.add]
    revision_count: int
    supervisor_decision: str | None

    # --- handoffs (serialized handoff envelopes, kept for the trace) ---------------
    handoffs: Annotated[list[str], operator.add]

    # --- writer / approval ----------------------------------------------------------
    final_report: FinalReport | None
    approval_status: str | None
    approval_feedback: str | None
    human_revision_count: int

    # --- observability -----------------------------------------------------------------
    execution_log: Annotated[list[ExecutionLogEntry], operator.add]
    errors: Annotated[list[WorkflowError], operator.add]


def initial_state(*, run_id: str, user_request: str, deliverable_hint: str | None, started_at: str) -> ResearchState:
    """Construct a fresh, fully-initialized state for a new run."""

    return ResearchState(
        run_id=run_id,
        user_request=user_request,
        deliverable_hint=deliverable_hint,
        started_at=started_at,
        updated_at=started_at,
        clarifications=[],
        clarification_round=0,
        needs_clarification=False,
        pending_clarification_question=None,
        research_objective="",
        research_questions=[],
        deliverable="",
        constraints=[],
        comparison_criteria=[],
        time_horizon=None,
        missing_information=[],
        entities=[],
        task_plan=[],
        task_plan_rationale="",
        current_task=None,
        active_tasks=[],
        completed_tasks=[],
        workflow_status="received",
        evidence=[],
        analysis=None,
        bonus_insights=[],
        critic_feedback=[],
        revision_count=0,
        supervisor_decision=None,
        handoffs=[],
        final_report=None,
        approval_status=None,
        approval_feedback=None,
        human_revision_count=0,
        execution_log=[],
        errors=[],
    )
