"""
database/repository.py
------------------------
Every database read/write in the whole app goes through a function in
this file. Nothing else — tools, agent nodes, Flask routes — should
import SQLAlchemy directly or build its own queries. That keeps storage
logic in exactly one place, so if the database ever changes, only this
file needs to change.
"""

import json
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker, Session

from config import settings
from database.models import Base, Task, Note, Reminder, ExecutionLog, Priority, Status, utc_now
from schemas import TaskCreate, TaskUpdate, TaskOut, NoteCreate, NoteUpdate, NoteOut, ReminderCreate, ReminderOut, ExecutionLogOut


# ============================================================
# ENGINE + SESSION SETUP
# ============================================================

_engine = create_engine(settings.DATABASE_URL, echo=False)
_SessionLocal = sessionmaker(bind=_engine)


def init_db() -> None:
    """Create all tables if they don't already exist. Call this once at startup."""
    Base.metadata.create_all(_engine)


def reset_db() -> None:
    """
    Drop and recreate every table, wiping all data. Used by tests to
    guarantee a clean slate before each one — init_db() alone isn't
    enough for that, since it only creates tables that don't exist yet
    and leaves existing data untouched.
    """
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)


def get_session() -> Session:
    """Return a new database session. Caller is responsible for closing it."""
    return _SessionLocal()


# ============================================================
# CONVERSION HELPERS
# ------------------------------------------------------------
# Tags are stored as a comma-separated string in the database, but the
# rest of the app works with real Python lists. These helpers do that
# conversion explicitly in both directions, instead of relying on
# Pydantic's automatic field-matching (which would silently mismatch
# on this one field, since a string and a list aren't compatible types).
# ============================================================

def _tags_to_string(tags: list[str]) -> str:
    return ", ".join(tag.strip() for tag in tags if tag.strip())


def _task_to_schema(task: Task) -> TaskOut:
    return TaskOut(
        task_id=task.task_id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        status=task.status,
        due_date=task.due_date,
        created_date=task.created_date,
        updated_date=task.updated_date,
        tags=task.tag_list(),
        source=task.source,
        notes=task.notes,
    )


def _note_to_schema(note: Note) -> NoteOut:
    return NoteOut(
        note_id=note.note_id,
        title=note.title,
        content=note.content,
        category=note.category,
        tags=note.tag_list(),
        created_date=note.created_date,
        updated_date=note.updated_date,
    )


# ============================================================
# TASK FUNCTIONS
# ============================================================

def create_task(data: TaskCreate) -> TaskOut:
    """Insert a new task and return it (Tool 1: Create Task)."""
    session = get_session()
    try:
        task = Task(
            title=data.title,
            description=data.description,
            priority=data.priority,
            due_date=data.due_date,
            tags=_tags_to_string(data.tags),
            source=data.source,
            notes=data.notes,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return _task_to_schema(task)
    finally:
        session.close()


def get_task(task_id: str) -> TaskOut | None:
    """Look up a single task by its ID. Returns None if it doesn't exist."""
    session = get_session()
    try:
        task = session.get(Task, task_id)
        return _task_to_schema(task) if task else None
    finally:
        session.close()


def list_tasks(
    status: Status | None = None,
    priority: Priority | None = None,
    tag: str | None = None,
    due_before=None,
) -> list[TaskOut]:
    """Return tasks matching the given filters (Tool 2: List Tasks). Any filter left as None is ignored."""
    session = get_session()
    try:
        query = session.query(Task)

        if status is not None:
            query = query.filter(Task.status == status)
        if priority is not None:
            query = query.filter(Task.priority == priority)
        if tag is not None:
            query = query.filter(Task.tags.contains(tag))
        if due_before is not None:
            query = query.filter(Task.due_date.isnot(None)).filter(Task.due_date <= due_before)

        tasks = query.order_by(Task.created_date.desc()).all()
        return [_task_to_schema(task) for task in tasks]
    finally:
        session.close()


def update_task(task_id: str, data: TaskUpdate) -> TaskOut | None:
    """
    Apply changes to an existing task (Tool 3: Update Task).
    Only fields actually present in `data` are changed — everything
    else is left as-is. Returns None if the task doesn't exist.
    """
    session = get_session()
    try:
        task = session.get(Task, task_id)
        if task is None:
            return None

        if data.title is not None:
            task.title = data.title
        if data.description is not None:
            task.description = data.description
        if data.priority is not None:
            task.priority = data.priority
        if data.due_date is not None:
            task.due_date = data.due_date
        if data.status is not None:
            task.status = data.status
        if data.tags is not None:
            task.tags = _tags_to_string(data.tags)
        if data.notes is not None:
            task.notes = data.notes

        task.updated_date = utc_now()
        session.commit()
        session.refresh(task)
        return _task_to_schema(task)
    finally:
        session.close()


def complete_task(task_id: str) -> TaskOut | None:
    """Mark a task as Completed (Tool 4: Complete Task). Returns None if it doesn't exist."""
    return update_task(task_id, TaskUpdate(task_id=task_id, status=Status.COMPLETED))


def delete_task(task_id: str) -> bool:
    """Permanently remove a task. Returns True if it existed and was deleted."""
    session = get_session()
    try:
        task = session.get(Task, task_id)
        if task is None:
            return False
        session.delete(task)
        session.commit()
        return True
    finally:
        session.close()


# ============================================================
# NOTE FUNCTIONS
# ============================================================

def create_note(data: NoteCreate) -> NoteOut:
    """Save a new note (Tool 6: Save Note)."""
    session = get_session()
    try:
        note = Note(
            title=data.title,
            content=data.content,
            category=data.category,
            tags=_tags_to_string(data.tags),
        )
        session.add(note)
        session.commit()
        session.refresh(note)
        return _note_to_schema(note)
    finally:
        session.close()


def update_note(note_id: str, data: NoteUpdate) -> NoteOut | None:
    """
    Apply changes to an existing note. Only fields actually present in
    `data` are changed. Returns None if the note doesn't exist.
    """
    session = get_session()
    try:
        note = session.get(Note, note_id)
        if note is None:
            return None

        if data.title is not None:
            note.title = data.title
        if data.content is not None:
            note.content = data.content
        if data.category is not None:
            note.category = data.category
        if data.tags is not None:
            note.tags = _tags_to_string(data.tags)

        note.updated_date = utc_now()
        session.commit()
        session.refresh(note)
        return _note_to_schema(note)
    finally:
        session.close()


def delete_note(note_id: str) -> bool:
    """Permanently remove a note. Returns True if it existed and was deleted."""
    session = get_session()
    try:
        note = session.get(Note, note_id)
        if note is None:
            return False
        session.delete(note)
        session.commit()
        return True
    finally:
        session.close()


def list_notes() -> list[NoteOut]:
    """Return every saved note, most recently updated first."""
    session = get_session()
    try:
        notes = session.query(Note).order_by(Note.updated_date.desc()).all()
        return [_note_to_schema(note) for note in notes]
    finally:
        session.close()


def search_notes(query_text: str, category: str | None = None, date_from=None, date_to=None) -> list[NoteOut]:
    """
    Search notes by keyword (Tool 5: Search Notes).

    This is a simple keyword match on the title and content for now —
    good enough for Week 3. Semantic search (matching by meaning rather
    than exact words) is recommended but explicitly optional at this
    stage, and can be added later without changing this function's
    signature or how it's called.
    """
    session = get_session()
    try:
        db_query = session.query(Note).filter(
            or_(
                Note.title.contains(query_text),
                Note.content.contains(query_text),
            )
        )

        if category is not None:
            db_query = db_query.filter(Note.category == category)
        if date_from is not None:
            db_query = db_query.filter(Note.created_date >= date_from)
        if date_to is not None:
            db_query = db_query.filter(Note.created_date <= date_to)

        notes = db_query.order_by(Note.updated_date.desc()).all()
        return [_note_to_schema(note) for note in notes]
    finally:
        session.close()


# ============================================================
# REMINDER FUNCTIONS (Bonus tool: Create Reminder)
# ============================================================

def _reminder_to_schema(reminder: Reminder) -> ReminderOut:
    return ReminderOut(
        reminder_id=reminder.reminder_id,
        message=reminder.message,
        remind_at=reminder.remind_at,
        task_id=reminder.task_id,
        created_date=reminder.created_date,
    )


def create_reminder(data: ReminderCreate) -> ReminderOut:
    """Insert a new reminder and return it."""
    session = get_session()
    try:
        reminder = Reminder(
            message=data.message,
            remind_at=data.remind_at,
            task_id=data.task_id,
        )
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        return _reminder_to_schema(reminder)
    finally:
        session.close()


# ============================================================
# EXECUTION LOG FUNCTIONS (Requirement 10)
# ============================================================

def _log_to_schema(log: ExecutionLog) -> ExecutionLogOut:
    return ExecutionLogOut(
        run_id=log.run_id,
        user_request=log.user_request,
        selected_model=log.selected_model,
        tools_called=json.loads(log.tools_called),
        tool_arguments=json.loads(log.tool_arguments),
        tool_results=json.loads(log.tool_results),
        approval_status=log.approval_status,
        error=log.error,
        start_time=log.start_time,
        end_time=log.end_time,
        duration_seconds=log.duration_seconds,
        final_outcome=log.final_outcome,
    )


def create_execution_log(
    user_request,
    selected_model,
    tools_called,
    tool_arguments,
    tool_results,
    approval_status,
    error,
    start_time,
    end_time,
    duration_seconds,
    final_outcome,
) -> ExecutionLogOut:
    """
    Save one completed agent run. Called once per run_agent() call —
    never stores API keys or private chain-of-thought, only the
    operational record Requirement 10 asks for.
    """
    session = get_session()
    try:
        log = ExecutionLog(
            user_request=user_request,
            selected_model=selected_model,
            tools_called=json.dumps(tools_called),
            tool_arguments=json.dumps(tool_arguments, default=str),
            tool_results=json.dumps(tool_results, default=str),
            approval_status=approval_status,
            error=error or "",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            final_outcome=final_outcome,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        return _log_to_schema(log)
    finally:
        session.close()


def list_execution_logs(limit: int = 50) -> list:
    """Return the most recent execution logs, newest first."""
    session = get_session()
    try:
        logs = session.query(ExecutionLog).order_by(ExecutionLog.start_time.desc()).limit(limit).all()
        return [_log_to_schema(log) for log in logs]
    finally:
        session.close()


def get_execution_log(run_id: str):
    """Look up a single execution log by its run ID. Returns None if it doesn't exist."""
    session = get_session()
    try:
        log = session.get(ExecutionLog, run_id)
        return _log_to_schema(log) if log else None
    finally:
        session.close()
