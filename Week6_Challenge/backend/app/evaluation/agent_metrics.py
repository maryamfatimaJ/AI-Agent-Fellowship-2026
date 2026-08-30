"""Agent-specific evaluation metrics computed from an orchestrator turn's
captured tool-call trace, reusing that trace directly rather than re-deriving
it — this module never re-executes anything, it only scores what the
orchestrator already recorded.

Mapping from the required agent-evaluation dimensions to what's actually
computed here, since this is a single-agent system with single-decision
eval cases (each tool_use case names exactly one expected tool call):

- intent understanding -> `intent_understood`: approximated as "did the
  agent pick the tool that correctly reflects the user's request". A wrong
  tool choice is itself evidence of a misunderstood intent; there's no
  separate signal to check intent independently of tool selection here.
- tool selection / argument generation -> `tool_selection_correct` /
  `tool_arguments_correct`: direct checks against the case's expected_tool
  and expected_args.
- planning / routing -> collapses into tool selection in a single-tool,
  single-step system: "routing" IS "which tool got selected". Multi-step
  planning across several tool calls is not exercised by this dataset
  version (every tool_use case is a single decision) — not fabricated here.
- state management -> out of scope for the same reason (no multi-step case
  exists yet to carry state between steps); `loop_count` is the closest
  available proxy (whether the agent needed more than one step at all).
- task completion / loop frequency / recovery behavior -> `task_completed`,
  `loop_count`/`hit_loop_limit`, `recovered_from_error`.
- multi-agent metrics (routing accuracy across agents, handoff success rate,
  revision count, unnecessary agent calls) -> **not applicable**: this
  application has exactly one agent (app/agent/orchestrator.py), not a
  multi-agent system, so there is no handoff or inter-agent routing to
  measure. Documented here rather than fabricating placeholder numbers.
"""

from dataclasses import dataclass

from app.evaluation.dataset import EvalCase
from app.evaluation.deterministic_evaluators import tool_args_correct, tool_selection_correct


@dataclass
class AgentCaseMetrics:
    intent_understood: bool | None = None
    tool_selection_correct: bool | None = None
    tool_arguments_correct: bool | None = None
    task_completed: bool | None = None
    loop_count: int = 0
    hit_loop_limit: bool = False
    recovered_from_error: bool | None = None
    required_approval_correctly: bool | None = None


def evaluate_agent_case(
    case: EvalCase,
    steps: list[dict],
    hit_loop_limit: bool,
    pending_action_id: str | None,
    final_text: str,
) -> AgentCaseMetrics:
    if case.expected_tool is None:
        return AgentCaseMetrics(loop_count=len(steps), hit_loop_limit=hit_loop_limit)

    first_step = steps[0] if steps else None
    actual_tool = first_step.get("tool") if first_step else None
    actual_args = first_step.get("arguments") if first_step else None

    tool_ok = tool_selection_correct(actual_tool, case.expected_tool)
    args_ok = tool_args_correct(actual_args, case.expected_args)

    required_approval_ok = None
    if case.expected_behavior == "requires_approval":
        required_approval_ok = pending_action_id is not None

    recovered = None
    if first_step and first_step.get("error"):
        recovered = bool(final_text) and "error" not in final_text.lower()

    task_completed = bool(tool_ok and args_ok and not hit_loop_limit)
    if required_approval_ok is not None:
        task_completed = task_completed and required_approval_ok

    return AgentCaseMetrics(
        intent_understood=tool_ok,  # see module docstring for why these are the same signal here
        tool_selection_correct=tool_ok,
        tool_arguments_correct=args_ok,
        task_completed=task_completed,
        loop_count=len(steps),
        hit_loop_limit=hit_loop_limit,
        recovered_from_error=recovered,
        required_approval_correctly=required_approval_ok,
    )


def aggregate_agent_metrics(per_case: list[AgentCaseMetrics]) -> dict:
    applicable = [m for m in per_case if m.tool_selection_correct is not None]
    if not applicable:
        return {}

    def _rate(predicate) -> float:
        return round(sum(1 for m in applicable if predicate(m)) / len(applicable), 3)

    recovery_applicable = [m for m in applicable if m.recovered_from_error is not None]

    return {
        "n_cases": len(applicable),
        "intent_understanding_accuracy": _rate(lambda m: m.intent_understood),
        "tool_selection_accuracy": _rate(lambda m: m.tool_selection_correct),
        "tool_argument_accuracy": _rate(lambda m: m.tool_arguments_correct),
        "task_completion_rate": _rate(lambda m: m.task_completed),
        "avg_loop_count": round(sum(m.loop_count for m in applicable) / len(applicable), 2),
        "loop_limit_hit_rate": _rate(lambda m: m.hit_loop_limit),
        "recovery_rate": (
            round(sum(1 for m in recovery_applicable if m.recovered_from_error) / len(recovery_applicable), 3)
            if recovery_applicable
            else None
        ),
        "multi_agent_metrics": "not_applicable_single_agent_system",
    }
