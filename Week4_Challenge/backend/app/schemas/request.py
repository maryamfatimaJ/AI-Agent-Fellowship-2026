"""Schemas for the raw user request and the Supervisor's structured extraction
of it (the "Request Analysis" stage of the workflow)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserRequest(BaseModel):
    """The raw, unstructured research request submitted by a user."""

    text: str = Field(..., min_length=3, description="The free-form research question or objective.")
    deliverable_hint: str | None = Field(
        default=None, description="Optional hint about the desired output format, e.g. 'decision brief'."
    )


class StructuredRequest(BaseModel):
    """The Supervisor's structured extraction of a user request.

    This is the schema the Supervisor Agent must populate during the
    "Request Analysis" stage. `is_ambiguous` and `missing_information`
    together drive the conditional clarification edge.
    """

    objective: str = Field(..., description="The single, clear research objective.")
    research_questions: list[str] = Field(
        default_factory=list, description="Concrete, independently-answerable research questions."
    )
    deliverable: str = Field(..., description="What the final output should be, e.g. 'decision brief with recommendation'.")
    constraints: list[str] = Field(default_factory=list, description="Explicit constraints (budget, geography, timeline, etc.).")
    comparison_criteria: list[str] = Field(
        default_factory=list, description="Dimensions to compare across, if the request involves comparing options."
    )
    time_horizon: str | None = Field(default=None, description="The time horizon the decision applies to, if any.")
    missing_information: list[str] = Field(
        default_factory=list, description="Information required to proceed confidently but absent from the request."
    )
    is_ambiguous: bool = Field(
        default=False, description="True if missing_information is significant enough to require user clarification."
    )
    clarification_question: str | None = Field(
        default=None,
        description="A single, specific question to ask the user, required when is_ambiguous is true.",
    )
    entities: list[str] = Field(
        default_factory=list,
        description="Named entities (products, companies, markets) the research should be scoped around.",
    )


class ClarificationExchange(BaseModel):
    """One round of supervisor-asks / user-answers clarification."""

    question: str
    answer: str | None = None
    round_number: int = 1
