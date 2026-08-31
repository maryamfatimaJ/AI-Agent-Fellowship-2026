"""Bounded tool-calling agent loop. Additive to chat_service.send_message —
existing plain chat is untouched; this only runs when a caller explicitly
opts into mode="agent" (see conversations.py::post_message).

Loop shape: ask the model (with tools) -> if it answers, stop -> if it calls
a tool, run it (or, for a HIGH-risk tool, park it as a PendingAction and stop
so a human can approve it) and feed the result back as the next turn ->
repeat up to agent_max_iterations. Loop prevention: refuses to run the exact
same (tool, arguments) pair twice in one turn.
"""

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agent.tools import TOOL_REGISTRY, RiskLevel, ToolResult, execute_tool
from app.core.config import get_settings
from app.core.events import TOOL_FAILED, TOOL_SELECTED, TOOL_SUCCEEDED, log_event
from app.core.retry import run_with_timeout
from app.guardrails import GuardrailBlockedError
from app.guardrails.input_guard import check_input
from app.guardrails.output_guard import check_output
from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message, MessageRole
from app.models.guardrail_event import GuardrailAction, GuardrailDirection, PendingAction
from app.models.prompt_version import PromptVersion
from app.models.trace import TraceStatus, TraceType
from app.services.guardrail_service import record_guardrail_event
from app.services.llm_service import (
    LLMError,
    LLMTimeoutError,
    default_model_for_provider,
    generate_with_tools,
    user_facing_error,
)
from app.services.trace_service import SpanRecorder, record_trace, timed_span
from app.services.usage_service import estimate_cost_breakdown, record_usage

logger = logging.getLogger("app.agent.orchestrator")

_TOOL_SPECS_FOR_LLM = [
    {"name": spec.name, "description": spec.description, "parameters": spec.parameters}
    for spec in TOOL_REGISTRY.values()
]

_AGENT_SYSTEM_SUFFIX = (
    "\n\nYou have tools available and should use them when they would help answer "
    "the user's request; otherwise answer directly without calling a tool. Never "
    "call the same tool with the same arguments more than once — if it didn't "
    "help the first time, try something else or answer with what you have."
)


@dataclass
class AgentStep:
    tool_name: str
    arguments: dict
    result: dict | None = None
    error: str | None = None


@dataclass
class AgentTurnOutcome:
    final_text: str
    steps: list[AgentStep] = field(default_factory=list)
    pending_action_id: str | None = None
    hit_loop_limit: bool = False


def _call_signature(name: str, arguments: dict) -> tuple[str, str]:
    return name, json.dumps(arguments or {}, sort_keys=True)


def run_agent_turn(
    conversation: Conversation,
    assistant: Assistant,
    user_content: str,
    user_id: str,
    db: Session,
) -> tuple[Message, Message, AgentTurnOutcome]:
    settings = get_settings()

    spans = SpanRecorder()
    spans.add("request", 0.0, status="success", user_input_length=len(user_content))

    with timed_span() as validation_span:
        input_check = check_input(user_content)
    if not input_check.allowed:
        record_guardrail_event(
            db,
            direction=GuardrailDirection.INPUT,
            guardrail_type="prompt_injection" if input_check.triggered_patterns else "input_validation",
            triggered=True,
            action=GuardrailAction.BLOCKED,
            workspace_id=conversation.workspace_id,
            conversation_id=conversation.id,
            detail={"patterns": input_check.triggered_patterns, "reason": input_check.reason},
        )
        raise GuardrailBlockedError(input_check.reason or "Message blocked by guardrails.", input_check.triggered_patterns)

    spans.add(
        "input_validation",
        validation_span["elapsed_ms"],
        status="flagged" if input_check.triggered_patterns else "success",
        triggered_patterns=input_check.triggered_patterns,
    )

    user_message = Message(conversation_id=conversation.id, role=MessageRole.USER, content=user_content)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    if input_check.triggered_patterns:
        record_guardrail_event(
            db,
            direction=GuardrailDirection.INPUT,
            guardrail_type="prompt_injection",
            triggered=True,
            action=GuardrailAction.FLAGGED,
            workspace_id=conversation.workspace_id,
            conversation_id=conversation.id,
            message_id=user_message.id,
            detail={"patterns": input_check.triggered_patterns},
        )

    if conversation.title is None:
        conversation.title = user_content[:60]
        db.commit()

    system_prompt = (assistant.system_prompt or "You are a helpful assistant.") + _AGENT_SYSTEM_SUFFIX
    history: list[dict[str, str]] = [{"role": "user", "content": user_content}]

    steps: list[AgentStep] = []
    seen_calls: set[tuple[str, str]] = set()
    hit_loop_limit = False
    pending_action_id: str | None = None
    final_text = ""
    total_input_tokens = total_output_tokens = 0
    trace_status = TraceStatus.SUCCESS
    trace_error: str | None = None

    with timed_span() as agent_span:
        for iteration in range(settings.agent_max_iterations):
            with timed_span() as model_span:
                try:
                    result = generate_with_tools(
                        system_prompt=system_prompt,
                        history=history,
                        tools=_TOOL_SPECS_FOR_LLM,
                        temperature=assistant.temperature,
                        max_tokens=assistant.max_tokens,
                        provider=assistant.model_provider,
                        model=assistant.model_name,
                    )
                except LLMTimeoutError as exc:
                    logger.warning("Agent turn timed out: %s", exc)
                    final_text = user_facing_error(exc)
                    trace_status = TraceStatus.TIMEOUT
                    trace_error = str(exc)
                    spans.add("agent_decision", model_span["elapsed_ms"], status="timeout", iteration=iteration)
                    break
                except LLMError as exc:
                    logger.warning("Agent turn LLM call failed: %s", exc)
                    final_text = user_facing_error(exc)
                    trace_status = TraceStatus.ERROR
                    trace_error = str(exc)
                    spans.add("agent_decision", model_span["elapsed_ms"], status="error", iteration=iteration)
                    break
            spans.add(
                "agent_decision",
                model_span["elapsed_ms"],
                status="success",
                iteration=iteration,
                chose_tool=bool(result.tool_calls),
            )

            total_input_tokens += result.input_tokens
            total_output_tokens += result.output_tokens

            if not result.tool_calls:
                final_text = result.text or ""
                break

            call = result.tool_calls[0]
            signature = _call_signature(call.name, call.arguments)
            if signature in seen_calls:
                logger.warning("Agent loop detected: repeated call to %s with identical arguments", call.name)
                hit_loop_limit = True
                final_text = (
                    "I wasn't able to make progress without repeating the same step, "
                    "so I'm stopping here rather than looping."
                )
                break
            seen_calls.add(signature)

            spec = TOOL_REGISTRY.get(call.name)
            if spec is None:
                history.append({"role": "assistant", "content": f"(requested unknown tool '{call.name}'; ignoring)"})
                continue

            log_event(logger, TOOL_SELECTED, tool_name=call.name, risk_level=spec.risk_level.value, iteration=iteration)

            if spec.risk_level == RiskLevel.HIGH:
                pending_action = PendingAction(
                    workspace_id=conversation.workspace_id,
                    conversation_id=conversation.id,
                    requested_by=user_id,
                    tool_name=call.name,
                    tool_args=call.arguments,
                    risk_level=spec.risk_level.value,
                )
                db.add(pending_action)
                db.commit()
                db.refresh(pending_action)
                pending_action_id = pending_action.id
                final_text = (
                    f"This action ('{call.name}') is high-risk and needs your approval before I can "
                    "proceed. Review and approve or reject it, then ask again."
                )
                steps.append(AgentStep(tool_name=call.name, arguments=call.arguments, error="awaiting_approval"))
                spans.add("tool_call", 0.0, status="pending_approval", tool_name=call.name)
                break

            spans.add("tool_call", 0.0, status="dispatched", tool_name=call.name, arguments=call.arguments)
            with timed_span() as tool_span:
                try:
                    tool_result = run_with_timeout(
                        lambda: execute_tool(
                            call.name,
                            call.arguments,
                            workspace_id=conversation.workspace_id,
                            user_id=user_id,
                            db=db,
                            conversation=conversation,
                        ),
                        settings.tool_timeout_seconds,
                    )
                except TimeoutError:
                    logger.warning("Tool '%s' timed out after %ss", call.name, settings.tool_timeout_seconds)
                    tool_result = ToolResult(error=f"Tool '{call.name}' timed out after {settings.tool_timeout_seconds}s")
            steps.append(
                AgentStep(tool_name=call.name, arguments=call.arguments, result=tool_result.output, error=tool_result.error)
            )
            spans.add(
                "tool_result",
                tool_span["elapsed_ms"],
                status="error" if tool_result.error else "success",
                tool_name=call.name,
            )

            if tool_result.error:
                log_event(logger, TOOL_FAILED, tool_name=call.name, error=tool_result.error)
                history.append(
                    {
                        "role": "assistant",
                        "content": f"Tool '{call.name}' failed: {tool_result.error}. Try a different approach or answer directly.",
                    }
                )
            else:
                log_event(logger, TOOL_SUCCEEDED, tool_name=call.name)
                history.append({"role": "assistant", "content": f"Tool '{call.name}' returned: {tool_result.output}"})
        else:
            hit_loop_limit = True
            final_text = "I wasn't able to finish this within the allowed number of steps."

    output_check = check_output(final_text, system_prompt)
    if output_check.triggered_patterns or output_check.secrets_found:
        final_text = output_check.text
        record_guardrail_event(
            db,
            direction=GuardrailDirection.OUTPUT,
            guardrail_type="secret_leak" if output_check.secrets_found else "output_leak",
            triggered=True,
            action=GuardrailAction.SANITIZED if output_check.sanitized else GuardrailAction.FLAGGED,
            workspace_id=conversation.workspace_id,
            conversation_id=conversation.id,
            detail={
                "patterns": output_check.triggered_patterns,
                "system_prompt_leaked": output_check.system_prompt_leaked,
                "secrets_found": output_check.secrets_found,
            },
        )

    spans.add("final_response", 0.0, status="success", output_length=len(final_text), hit_loop_limit=hit_loop_limit)

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=final_text,
        citations=None,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    model_name = assistant.model_name or default_model_for_provider(assistant.model_provider)
    active_prompt_version = (
        db.query(PromptVersion)
        .filter(PromptVersion.workspace_id == conversation.workspace_id, PromptVersion.is_active.is_(True))
        .first()
    )
    if total_input_tokens or total_output_tokens:
        record_usage(
            db, user_id, conversation.workspace_id, assistant.model_provider, model_name,
            total_input_tokens, total_output_tokens,
        )

    input_cost, output_cost, total_cost = estimate_cost_breakdown(model_name, total_input_tokens, total_output_tokens)
    record_trace(
        db,
        trace_type=TraceType.TOOL_CALL,
        workspace_id=conversation.workspace_id,
        user_id=user_id,
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        provider=assistant.model_provider,
        model=model_name,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        cost_usd=total_cost,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        latency_ms=agent_span["elapsed_ms"],
        status=trace_status,
        error_message=trace_error,
        meta={
            "steps": [
                {"tool": s.tool_name, "arguments": s.arguments, "result": s.result, "error": s.error} for s in steps
            ],
            "spans": spans.spans,
            "iteration_count": len(steps),
            "hit_loop_limit": hit_loop_limit,
            "pending_action_id": pending_action_id,
            "total_tokens": total_input_tokens + total_output_tokens,
            "prompt_version": active_prompt_version.version_label if active_prompt_version else "unversioned",
            "input_preview": user_content[:200],
            "output_preview": final_text[:200],
        },
    )

    outcome = AgentTurnOutcome(
        final_text=final_text, steps=steps, pending_action_id=pending_action_id, hit_loop_limit=hit_loop_limit
    )
    return user_message, assistant_message, outcome
