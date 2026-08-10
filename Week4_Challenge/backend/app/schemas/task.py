"""Task planning schemas. The Supervisor builds these dynamically from the
StructuredRequest — never hardcoded."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import AgentName, TaskPriority, TaskStatus


class ResearchTask(BaseModel):
    """A single unit of work the Supervisor assigns to a specialist agent."""

    task_id: str
    description: str = Field(..., description="What this task must accomplish.")
    research_question: str = Field(..., description="The research question this task answers.")
    assigned_agent: AgentName = AgentName.RESEARCH
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: list[str] = Field(default_factory=list, description="task_ids that must complete first.")
    status: TaskStatus = TaskStatus.PENDING
    entity: str | None = Field(default=None, description="The entity (product/company/option) this task targets, if any.")


class TaskPlan(BaseModel):
    """The full dynamically-generated plan for a research run."""

    tasks: list[ResearchTask] = Field(default_factory=list)
    rationale: str = Field(default="", description="Why the plan is shaped this way.")

    def independent_tasks(self) -> list[ResearchTask]:
        """Tasks with no unmet dependencies — safe to run in parallel."""

        completed_ids = {t.task_id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        return [
            t
            for t in self.tasks
            if t.status == TaskStatus.PENDING and all(dep in completed_ids for dep in t.dependencies)
        ]
