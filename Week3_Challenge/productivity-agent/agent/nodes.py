"""
agent/nodes.py
------------------
The two core operations the agent controller (agent/graph.py) calls on
every step: decide what to do next, and safely execute a tool.
"""

import concurrent.futures
from pydantic import ValidationError

from config import settings
from services.llm_service import generate_json, LLMError, LLMQuotaExceededError
from tools.registry import get_tool, TOOL_REGISTRY
from agent.state import AgentDecision
from agent.prompts import build_decision_prompt


class DecisionError(Exception):
    """Raised when the LLM's decision can't be understood or trusted."""
    pass


class ToolExecutionError(Exception):
    """Raised when a tool fails to run correctly, after retries are exhausted."""
    pass


# ============================================================
# BUILD THE TOOL DESCRIPTION LIST FOR THE PROMPT
# ============================================================

def build_tool_descriptions():
    """Turn the tool registry into a plain-text list the LLM can read."""
    lines = []
    for name, tool_def in TOOL_REGISTRY.items():
        lines.append("- " + name + ": " + tool_def.description)
    return "\n".join(lines)


# ============================================================
# DECISION NODE
# ============================================================

def _ask_llm_for_decision(prompt):
    """
    The actual call to the LLM for a decision. Split into its own tiny
    function so tests can replace just this one call with a canned
    response, without needing a real Gemini API key.
    """
    return generate_json(prompt)


def decide_next_action(
    user_request, prior_tool_results,
    conversation_history=None, last_shown_tasks=None, preferences=None, last_tool_result=None,
    current_date=None,
):
    """
    Ask the LLM what to do next: answer directly, call a tool, or ask
    for clarification. Raises DecisionError if the LLM can't be reached
    or its response doesn't match the required structure (Requirement 8:
    invalid model response).
    """
    tool_descriptions = build_tool_descriptions()
    prompt = build_decision_prompt(
        user_request, tool_descriptions, prior_tool_results,
        conversation_history=conversation_history,
        last_shown_tasks=last_shown_tasks,
        preferences=preferences,
        last_tool_result=last_tool_result,
        current_date=current_date,
    )

    try:
        raw_decision = _ask_llm_for_decision(prompt)
    except LLMError as error:
        raise DecisionError(str(error)) from error

    try:
        return AgentDecision.model_validate(raw_decision)
    except ValidationError as error:
        raise DecisionError(
            "The language model's decision didn't match the expected structure: " + str(error)
        ) from error


# ============================================================
# TOOL EXECUTION NODE
# ============================================================

def execute_tool_with_limits(tool_name, arguments):
    """
    Run a tool safely: validate its arguments, enforce a timeout, and
    retry on failure up to the configured limit (Requirement 9).

    Raises ToolExecutionError for any failure — unknown tool, invalid
    arguments, timeout, or repeated failures — with a message that's
    safe to show the user (no stack traces).
    """
    tool_def = get_tool(tool_name)
    if tool_def is None:
        raise ToolExecutionError("'" + tool_name + "' isn't a recognized tool.")

    # Validate arguments against the tool's own input schema first,
    # so a bad argument is caught clearly (Requirement 8) instead of
    # crashing deep inside the tool function.
    validated_input = None
    if tool_def.input_schema is not None:
        try:
            validated_input = tool_def.input_schema.model_validate(arguments)
        except ValidationError as error:
            raise ToolExecutionError(
                "Invalid input for '" + tool_name + "': " + str(error)
            ) from error

    last_error = None
    max_attempts = settings.MAX_TOOL_RETRIES + 1

    for attempt in range(1, max_attempts + 1):
        try:
            return _run_with_timeout(tool_def.function, validated_input, settings.TOOL_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            last_error = "'" + tool_name + "' took too long to respond (over " + str(settings.TOOL_TIMEOUT_SECONDS) + "s)."
        except LLMQuotaExceededError as error:
            # Retrying an exhausted daily quota can't succeed and only
            # burns more of the (already gone) request budget — fail
            # fast instead of spending all max_attempts on it.
            last_error = str(error)
            break
        except Exception as error:
            last_error = str(error)

    raise ToolExecutionError(
        "'" + tool_name + "' failed after " + str(attempt) + " attempt(s): " + str(last_error)
    )


def _run_with_timeout(function, argument, timeout_seconds):
    """Run a single function call with a hard timeout, using a worker thread."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        if argument is None:
            future = executor.submit(function)
        else:
            future = executor.submit(function, argument)
        return future.result(timeout=timeout_seconds)
