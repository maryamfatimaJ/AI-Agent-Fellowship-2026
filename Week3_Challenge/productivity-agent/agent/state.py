"""
agent/state.py
-----------------
The data shapes the agent controller passes around internally. These
are NOT the same as the Task/Note schemas in schemas.py — those
describe the app's data; these describe the agent's own thinking
process and execution record.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional, Any
from pydantic import BaseModel


class AgentDecision(BaseModel):
    """
    What the LLM decides to do next, on any given step. Exactly one of
    answer / tool_name / clarification_question should be filled in,
    depending on `action`.
    """

    action: Literal["answer", "call_tool", "ask_clarification"]
    answer: Optional[str] = None
    tool_name: Optional[str] = None
    tool_arguments: dict = {}
    clarification_question: Optional[str] = None
    user_preference: Optional[str] = None  # a short note if the user stated a preference this turn, e.g. "prefers morning scheduling"
    reasoning_summary: str = ""  # a SHORT operational note, e.g. "listing high-priority tasks" — never private chain-of-thought


@dataclass
class StepRecord:
    """One recorded step of an agent run, for the execution log (Requirement 10)."""
    stage: str  # "thinking", "selecting_tool", "executing", "waiting_approval", "done", "error"
    detail: str
    tool_name: Optional[str] = None
    tool_arguments: Optional[dict] = None
    tool_result: Optional[Any] = None


@dataclass
class PendingApproval:
    """A proposed action that needs the user's Approve/Reject before it runs."""
    tool_name: str
    tool_arguments: dict
    title: str
    description: str


@dataclass
class AgentResult:
    """What run_agent() hands back to app.py after a run finishes (or pauses for approval)."""
    final_response: Optional[str] = None
    pending_approval: Optional[PendingApproval] = None
    steps: list = field(default_factory=list)  # list[StepRecord]
    error: Optional[str] = None
