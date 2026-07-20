"""
tools/registry.py
--------------------
A single, central list of every tool the agent can call. The agent
controller (Phase 4) looks tools up here by name, instead of importing
each tools/*.py module directly — this is what "reusable tools" means
in practice: adding a new tool later means adding one entry here, not
changing agent logic.
"""

from dataclasses import dataclass
from typing import Callable, Type, Optional
from pydantic import BaseModel

from tools import task_tools, note_tools, planning_tools, reminder_tools, email_tools
from schemas import (
    TaskCreate,
    BulkCreateTasksInput,
    ListTasksInput,
    TaskUpdate,
    CompleteTaskInput,
    SearchNotesInput,
    NoteCreate,
    ExtractMeetingActionsInput,
    GenerateWorkPlanInput,
    ReminderCreate,
    DraftFollowUpEmailInput,
)


@dataclass
class ToolDefinition:
    """Everything the agent needs to know about one tool."""
    name: str
    description: str
    function: Callable
    input_schema: Optional[Type[BaseModel]]  # None for tools that take no input
    requires_approval: bool


TOOL_REGISTRY = {

    "create_task": ToolDefinition(
        name="create_task",
        description="Create a new task with a title, description, priority, due date, and tags.",
        function=task_tools.create_task,
        input_schema=TaskCreate,
        requires_approval=task_tools.TASK_1_REQUIRES_APPROVAL,
    ),

    "create_tasks_bulk": ToolDefinition(
        name="create_tasks_bulk",
        description="Create several tasks at once from a list (e.g. action items extracted from meeting notes). Always requires approval.",
        function=task_tools.create_tasks_bulk,
        input_schema=BulkCreateTasksInput,
        requires_approval=task_tools.TASK_1_BULK_REQUIRES_APPROVAL,
    ),

    "list_tasks": ToolDefinition(
        name="list_tasks",
        description="List tasks, optionally filtered by status, priority, tag, or due date (due_before).",
        function=task_tools.list_tasks,
        input_schema=ListTasksInput,
        requires_approval=task_tools.TASK_2_REQUIRES_APPROVAL,
    ),

    "update_task": ToolDefinition(
        name="update_task",
        description="Change a task's title, description, priority, due date, status, or tags.",
        function=task_tools.update_task,  # note: takes (task_id, data) — see agent/nodes.py for the call shape
        input_schema=TaskUpdate,
        requires_approval=task_tools.TASK_3_REQUIRES_APPROVAL,
    ),

    "complete_task": ToolDefinition(
        name="complete_task",
        description="Mark a task as Completed.",
        function=task_tools.complete_task,
        input_schema=CompleteTaskInput,
        requires_approval=task_tools.TASK_4_REQUIRES_APPROVAL,
    ),

    "search_notes": ToolDefinition(
        name="search_notes",
        description="Search saved notes by keyword, optionally within one category and/or a created-date range (date_from/date_to).",
        function=note_tools.search_notes,
        input_schema=SearchNotesInput,
        requires_approval=note_tools.SEARCH_NOTES_REQUIRES_APPROVAL,
    ),

    "save_note": ToolDefinition(
        name="save_note",
        description="Save a new note with a title, content, category, and tags.",
        function=note_tools.save_note,
        input_schema=NoteCreate,
        requires_approval=note_tools.SAVE_NOTE_REQUIRES_APPROVAL,
    ),

    "extract_meeting_actions": ToolDefinition(
        name="extract_meeting_actions",
        description="Extract a summary, decisions, action items, and open questions from meeting notes or a transcript.",
        function=planning_tools.extract_meeting_actions,
        input_schema=ExtractMeetingActionsInput,
        requires_approval=planning_tools.EXTRACT_MEETING_ACTIONS_REQUIRES_APPROVAL,
    ),

    "generate_work_plan": ToolDefinition(
        name="generate_work_plan",
        description="Build an ordered schedule from the current task list, given available hours and a date.",
        function=planning_tools.generate_work_plan,
        input_schema=GenerateWorkPlanInput,
        requires_approval=planning_tools.GENERATE_WORK_PLAN_REQUIRES_APPROVAL,
    ),

    "detect_overdue_tasks": ToolDefinition(
        name="detect_overdue_tasks",
        description="Find every task that's overdue and not yet completed or cancelled.",
        function=task_tools.detect_overdue_tasks,
        input_schema=None,
        requires_approval=task_tools.BONUS_DETECT_OVERDUE_REQUIRES_APPROVAL,
    ),

    "create_reminder": ToolDefinition(
        name="create_reminder",
        description="Create a reminder with a message and a time to be reminded, optionally tied to a task. Always requires approval.",
        function=reminder_tools.create_reminder,
        input_schema=ReminderCreate,
        requires_approval=reminder_tools.CREATE_REMINDER_REQUIRES_APPROVAL,
    ),

    "draft_follow_up_email": ToolDefinition(
        name="draft_follow_up_email",
        description="Draft (and simulate sending) a follow-up email to someone, given the context to follow up on. Always requires approval.",
        function=email_tools.draft_follow_up_email,
        input_schema=DraftFollowUpEmailInput,
        requires_approval=email_tools.DRAFT_FOLLOW_UP_EMAIL_REQUIRES_APPROVAL,
    ),
}


def get_tool(name):
    """Look up a tool by name. Returns None if no tool with that name exists."""
    return TOOL_REGISTRY.get(name)


def list_tool_names():
    """Return the names of every registered tool — useful for building the agent's system prompt."""
    return list(TOOL_REGISTRY.keys())
