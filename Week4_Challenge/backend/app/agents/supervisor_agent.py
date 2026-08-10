"""Supervisor Agent.

Responsibilities: understand the objective, extract a structured request,
detect ambiguity, build the dynamic task plan, monitor workflow progress,
and decide completion / recovery. The Supervisor never performs research
itself — that is strictly the Research Agent's job.
"""

from __future__ import annotations

from app.prompts.loader import render_prompt
from app.schemas.common import TaskStatus
from app.schemas.critic import CriticFeedback
from app.schemas.request import ClarificationExchange, StructuredRequest
from app.schemas.task import ResearchTask, TaskPlan
from app.services.llm_service import LLMCallResult, get_llm_service
from app.utils.ids import new_task_id

_SYSTEM_PROMPT = (
    "You are the Supervisor Agent inside Evident, a multi-agent research and "
    "decision-intelligence platform. You orchestrate specialist agents but "
    "never perform research yourself. Be precise, conservative about "
    "declaring ambiguity, and never fabricate information not present in "
    "the input. Respond only with the requested JSON."
)


async def analyze_request(
    *,
    user_request: str,
    deliverable_hint: str | None,
    clarifications: list[ClarificationExchange],
) -> tuple[StructuredRequest, LLMCallResult]:
    """Request Analysis stage: extract a StructuredRequest from raw input."""

    clarification_lines = [
        f"Q: {c.question}\nA: {c.answer or '(unanswered)'}" for c in clarifications
    ]
    prompt = render_prompt(
        "supervisor/request_analysis.md",
        user_request=user_request,
        deliverable_hint=deliverable_hint,
        clarifications=clarification_lines,
    )
    llm = get_llm_service()
    return await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
        response_model=StructuredRequest,
    )


async def build_task_plan(structured_request: StructuredRequest) -> tuple[TaskPlan, LLMCallResult]:
    """Dynamic Planning stage: derive an executable task plan from the brief.

    Never hardcoded — every task description, priority, and dependency is
    derived from the structured request by the LLM.
    """

    prompt = render_prompt(
        "supervisor/task_planning.md",
        objective=structured_request.objective,
        research_questions=structured_request.research_questions,
        deliverable=structured_request.deliverable,
        constraints=structured_request.constraints,
        comparison_criteria=structured_request.comparison_criteria,
        entities=structured_request.entities,
        time_horizon=structured_request.time_horizon,
    )
    llm = get_llm_service()
    plan, meta = await llm.generate_structured(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
        response_model=TaskPlan,
    )
    # Guarantee unique, well-formed task_ids and pending status regardless of
    # what the LLM produced — the graph's fan-out logic depends on this.
    normalized_tasks: list[ResearchTask] = []
    seen_ids: set[str] = set()
    for index, task in enumerate(plan.tasks, start=1):
        task_id = task.task_id if task.task_id and task.task_id not in seen_ids else new_task_id(index)
        seen_ids.add(task_id)
        normalized_tasks.append(task.model_copy(update={"task_id": task_id, "status": TaskStatus.PENDING}))
    plan = plan.model_copy(update={"tasks": normalized_tasks})
    return plan, meta


def decide_after_critic(
    *,
    feedback: CriticFeedback,
    revision_count: int,
    max_revision_cycles: int,
) -> tuple[str, str]:
    """Supervisor's deterministic completion/recovery decision after the
    Critic hands off its feedback.

    Returns a (decision, notes) tuple where decision is one of
    "advance_to_writer" or "send_back_for_revision". Deterministic by
    design: this gate must be reliable and testable without an LLM call.
    """

    if feedback.verdict.value == "approved":
        return "advance_to_writer", "Critic approved the analysis; releasing to the Writer agent."

    if revision_count >= max_revision_cycles:
        return (
            "advance_to_writer",
            f"Maximum revision cycles ({max_revision_cycles}) reached; advancing with caveats noted "
            "instead of looping indefinitely.",
        )

    return (
        "send_back_for_revision",
        f"Critic rejected the analysis (round {revision_count + 1}); sending back to the Analyst with "
        "required revisions.",
    )
