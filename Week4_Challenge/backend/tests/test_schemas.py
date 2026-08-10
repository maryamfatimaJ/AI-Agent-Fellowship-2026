"""Schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.common import TaskStatus
from app.schemas.evidence import EvidenceItem
from app.schemas.task import ResearchTask, TaskPlan


def _evidence(**overrides) -> EvidenceItem:
    defaults = dict(
        evidence_id="ev_0000000001",
        claim="Example claim",
        supporting_text="Example excerpt",
        source="https://example.com",
        source_title="Example",
        retrieved_at="2026-01-01T00:00:00+00:00",
        research_question="Is X true?",
        confidence=80,
        agent_id="research",
    )
    defaults.update(overrides)
    return EvidenceItem(**defaults)


def test_evidence_item_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        _evidence(confidence=150)
    with pytest.raises(ValidationError):
        _evidence(confidence=-1)


def test_evidence_item_accepts_boundary_confidence():
    assert _evidence(confidence=0).confidence == 0
    assert _evidence(confidence=100).confidence == 100


def test_task_plan_independent_tasks_respects_dependencies():
    plan = TaskPlan(
        tasks=[
            ResearchTask(task_id="t1", description="d1", research_question="q1", status=TaskStatus.PENDING),
            ResearchTask(
                task_id="t2",
                description="d2",
                research_question="q2",
                status=TaskStatus.PENDING,
                dependencies=["t1"],
            ),
        ]
    )

    independent = plan.independent_tasks()
    assert [t.task_id for t in independent] == ["t1"]

    plan.tasks[0].status = TaskStatus.COMPLETED
    independent_after = plan.independent_tasks()
    assert [t.task_id for t in independent_after] == ["t2"]


def test_task_plan_all_independent_when_no_dependencies():
    plan = TaskPlan(
        tasks=[
            ResearchTask(task_id="t1", description="d1", research_question="q1"),
            ResearchTask(task_id="t2", description="d2", research_question="q2"),
        ]
    )
    assert {t.task_id for t in plan.independent_tasks()} == {"t1", "t2"}
