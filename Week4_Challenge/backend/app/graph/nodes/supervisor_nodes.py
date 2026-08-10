"""Supervisor-owned graph nodes: request intake, request analysis,
clarification (interrupt), dynamic planning, the post-critic completion
decision, and the two terminal bookkeeping stages (finalize, execution log).

The Supervisor Agent never performs research itself — every node here only
understands, decomposes, routes, and decides; `app.agents.research_agent`
does the actual research work.
"""

from __future__ import annotations

from langgraph.types import interrupt

from app.agents import supervisor_agent
from app.agents.base import error_entry, log_entry
from app.config.logging_config import get_logger
from app.config.settings import get_settings
from app.schemas.common import ApprovalDecision, LogLevel, WorkflowStatus
from app.schemas.request import ClarificationExchange
from app.state.graph_state import ResearchState
from app.utils.errors import EvidentError
from app.utils.time_utils import utc_now_iso

logger = get_logger("graph.supervisor")


async def supervisor_intake_node(state: ResearchState) -> dict:
    """Entry point: acknowledge the request and hand off to Request Analysis."""

    logger.info("workflow.received", run_id=state["run_id"])
    return {
        "workflow_status": WorkflowStatus.ANALYZING_REQUEST.value,
        "execution_log": [
            log_entry("supervisor", f"Received research request: {state['user_request'][:200]}")
        ],
        "updated_at": utc_now_iso(),
    }


async def request_analysis_node(state: ResearchState) -> dict:
    """Extract a StructuredRequest from the raw request (+ any clarification
    answers so far), and decide whether clarification is still needed."""

    settings = get_settings()
    try:
        structured, meta = await supervisor_agent.analyze_request(
            user_request=state["user_request"],
            deliverable_hint=state.get("deliverable_hint"),
            clarifications=state.get("clarifications", []),
        )
    except EvidentError as exc:
        logger.error("request_analysis.failed", run_id=state["run_id"], error=str(exc))
        return {
            "errors": [error_entry("supervisor", exc, recoverable=False)],
            "workflow_status": WorkflowStatus.FAILED.value,
            "execution_log": [log_entry("supervisor", "Request analysis failed", level=LogLevel.ERROR)],
            "updated_at": utc_now_iso(),
        }

    clarification_round = state.get("clarification_round", 0)
    needs_clarification = structured.is_ambiguous and clarification_round < settings.max_clarification_rounds

    update: dict = {
        "research_objective": structured.objective,
        "research_questions": structured.research_questions,
        "deliverable": structured.deliverable,
        "constraints": structured.constraints,
        "comparison_criteria": structured.comparison_criteria,
        "time_horizon": structured.time_horizon,
        "missing_information": structured.missing_information,
        "entities": structured.entities,
        "needs_clarification": needs_clarification,
        "pending_clarification_question": structured.clarification_question if needs_clarification else None,
        "workflow_status": (
            WorkflowStatus.AWAITING_CLARIFICATION if needs_clarification else WorkflowStatus.PLANNING
        ).value,
        "execution_log": [
            log_entry(
                "supervisor",
                "Completed request analysis"
                + (" — clarification required" if needs_clarification else ""),
                duration_ms=meta.duration_ms,
            )
        ],
        "updated_at": utc_now_iso(),
    }
    return update


async def clarification_node(state: ResearchState) -> dict:
    """Pause the workflow and wait for a human answer via `interrupt()`.

    Resumed via `POST /clarification`, which calls the graph with
    `Command(resume=answer)`. On resume, this function continues executing
    from just after the `interrupt()` call with `answer` bound to the value
    the caller supplied.
    """

    question = state.get("pending_clarification_question") or (
        "Could you clarify the scope, entities, or constraints for this research request?"
    )
    round_number = state.get("clarification_round", 0) + 1

    answer: str = interrupt(
        {
            "type": "clarification_required",
            "question": question,
            "round": round_number,
        }
    )

    logger.info("clarification.resumed", run_id=state["run_id"], round=round_number)
    return {
        "clarifications": [ClarificationExchange(question=question, answer=answer, round_number=round_number)],
        "clarification_round": round_number,
        "needs_clarification": False,
        "pending_clarification_question": None,
        "workflow_status": WorkflowStatus.ANALYZING_REQUEST.value,
        "execution_log": [log_entry("human", f"Clarification round {round_number} answered")],
        "updated_at": utc_now_iso(),
    }


async def planning_node(state: ResearchState) -> dict:
    """Dynamic Task Planning: derive an executable, parallelizable task plan
    strictly from the structured request — never hardcoded."""

    from app.schemas.request import StructuredRequest  # local import avoids a cycle at module load time

    structured = StructuredRequest(
        objective=state["research_objective"],
        research_questions=state.get("research_questions", []),
        deliverable=state.get("deliverable", ""),
        constraints=state.get("constraints", []),
        comparison_criteria=state.get("comparison_criteria", []),
        time_horizon=state.get("time_horizon"),
        missing_information=state.get("missing_information", []),
        is_ambiguous=False,
        entities=state.get("entities", []),
    )

    try:
        plan, meta = await supervisor_agent.build_task_plan(structured)
    except EvidentError as exc:
        logger.error("planning.failed", run_id=state["run_id"], error=str(exc))
        return {
            "errors": [error_entry("supervisor", exc, recoverable=False)],
            "workflow_status": WorkflowStatus.FAILED.value,
            "execution_log": [log_entry("supervisor", "Task planning failed", level=LogLevel.ERROR)],
            "updated_at": utc_now_iso(),
        }

    return {
        "task_plan": plan.tasks,
        "task_plan_rationale": plan.rationale,
        "active_tasks": [t.task_id for t in plan.tasks],
        "workflow_status": WorkflowStatus.RESEARCHING.value,
        "execution_log": [
            log_entry(
                "supervisor",
                f"Built task plan with {len(plan.tasks)} independent task(s)",
                duration_ms=meta.duration_ms,
            )
        ],
        "updated_at": utc_now_iso(),
    }


async def supervisor_decision_node(state: ResearchState) -> dict:
    """Supervisor's completion/recovery decision after receiving the
    Critic → Supervisor handoff. Deterministic and fully testable without an
    LLM call: correctness of the revision-loop gate must not depend on model
    sampling."""

    settings = get_settings()
    feedback = state["critic_feedback"][-1]
    decision, notes = supervisor_agent.decide_after_critic(
        feedback=feedback,
        revision_count=state.get("revision_count", 0),
        max_revision_cycles=settings.max_revision_cycles,
    )

    from app.schemas.handoff import CriticToSupervisorHandoff, SupervisorToWriterHandoff
    from app.utils.ids import new_handoff_id

    handoffs = [CriticToSupervisorHandoff(handoff_id=new_handoff_id(), feedback=feedback).model_dump_json()]

    update: dict = {
        "supervisor_decision": decision,
        "execution_log": [log_entry("supervisor", notes)],
        "updated_at": utc_now_iso(),
    }

    if decision == "send_back_for_revision":
        update["revision_count"] = state.get("revision_count", 0) + 1
        update["workflow_status"] = WorkflowStatus.REVISING.value
        update["handoffs"] = handoffs
    else:
        handoffs.append(
            SupervisorToWriterHandoff(
                handoff_id=new_handoff_id(),
                analysis=state["analysis"],
                critic_feedback=feedback,
                decision_notes=notes,
            ).model_dump_json()
        )
        update["workflow_status"] = WorkflowStatus.WRITING_REPORT.value
        update["handoffs"] = handoffs

    return update


async def finalize_node(state: ResearchState) -> dict:
    """Compile the approval outcome into the final report's status."""

    is_rejected_final = state.get("approval_status") == ApprovalDecision.REJECTED.value
    report = state.get("final_report")
    if report is not None:
        report = report.model_copy(update={"approval_status": "rejected" if is_rejected_final else "approved"})

    return {
        "final_report": report,
        "workflow_status": (WorkflowStatus.REJECTED if is_rejected_final else WorkflowStatus.COMPLETED).value,
        "execution_log": [
            log_entry("supervisor", "Report finalized" if not is_rejected_final else "Report finalized as rejected")
        ],
        "updated_at": utc_now_iso(),
    }


async def execution_log_node(state: ResearchState) -> dict:
    """Terminal stage: close out the execution trace. The full compiled
    ExecutionTrace object is assembled on-demand by the API layer (see
    `app.services.execution_trace_service`) from these accumulated fields —
    this node just marks the run as fully closed."""

    return {
        "execution_log": [log_entry("supervisor", "Execution trace closed; workflow complete")],
        "updated_at": utc_now_iso(),
    }
