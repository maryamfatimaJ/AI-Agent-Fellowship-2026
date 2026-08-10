"""GET /tasks/{run_id} — the dynamically-generated task plan, with each
task's live status computed from `completed_tasks` / `errors` rather than a
static field, since task_plan itself is written once by the Supervisor and
never mutated afterward."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import TaskListOut
from app.schemas.common import TaskStatus
from app.services import workflow_service

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{run_id}", response_model=TaskListOut)
async def get_tasks(run_id: str) -> TaskListOut:
    snapshot = workflow_service.get_snapshot(run_id)
    values = snapshot.values

    completed_ids = set(values.get("completed_tasks", []))
    failed_ids = {error.task_id for error in values.get("errors", []) if error.task_id}

    tasks = []
    for task in values.get("task_plan", []):
        if task.task_id in failed_ids:
            status = TaskStatus.FAILED
        elif task.task_id in completed_ids:
            status = TaskStatus.COMPLETED
        elif task.task_id in set(values.get("active_tasks", [])):
            status = TaskStatus.IN_PROGRESS
        else:
            status = TaskStatus.PENDING
        tasks.append(task.model_copy(update={"status": status}))

    return TaskListOut(run_id=run_id, tasks=tasks)
