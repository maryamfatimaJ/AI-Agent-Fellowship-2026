"""
database/models.py
-------------------
SQLAlchemy ORM models — these define what actually gets stored in the
database. Pydantic schemas (see schemas.py) are a separate, deliberate
layer on top of these: models.py describes storage, schemas.py describes
validation at the boundaries (tool inputs/outputs). Keeping them separate
means a storage-only change (like adding an index) never has to touch
validation logic, and vice versa.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared base class every ORM model inherits from."""
    pass


class Priority(str, enum.Enum):
    """Allowed task priority values, per Requirement 2."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class Status(str, enum.Enum):
    """Allowed task status values, per Requirement 2."""
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    BLOCKED = "Blocked"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


def utc_now() -> datetime:
    """Current UTC time, timezone-aware (datetime.utcnow() is deprecated)."""
    return datetime.now(timezone.utc)


def generate_id() -> str:
    """Generate a short, unique ID string for a new Task or Note."""
    return str(uuid.uuid4())


class Task(Base):
    """A single task the user is tracking."""

    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_id)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[Priority] = mapped_column(SQLEnum(Priority), default=Priority.MEDIUM)
    status: Mapped[Status] = mapped_column(SQLEnum(Status), default=Status.PENDING)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_date: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_date: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
    tags: Mapped[str] = mapped_column(String, default="")  # stored as a comma-separated string
    source: Mapped[str] = mapped_column(String, default="user")  # e.g. "user", "meeting_notes"
    notes: Mapped[str] = mapped_column(Text, default="")

    def tag_list(self) -> list[str]:
        """Return this task's tags as a real Python list instead of a raw string."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]


class Note(Base):
    """A single saved note (e.g. from a meeting, or a personal reminder)."""

    __tablename__ = "notes"

    note_id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_id)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, default="general")
    tags: Mapped[str] = mapped_column(String, default="")
    created_date: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_date: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    def tag_list(self) -> list[str]:
        """Return this note's tags as a real Python list instead of a raw string."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]


class Reminder(Base):
    """A reminder the user asked the agent to set, optionally tied to a task."""

    __tablename__ = "reminders"

    reminder_id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_id)
    message: Mapped[str] = mapped_column(String, nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_date: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ExecutionLog(Base):
    """
    A record of one agent run, per Requirement 10. Every field the
    requirement lists is here EXCEPT API keys and private reasoning,
    which are deliberately never stored.
    """

    __tablename__ = "execution_logs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_id)
    user_request: Mapped[str] = mapped_column(Text, nullable=False)
    selected_model: Mapped[str] = mapped_column(String, default="")
    tools_called: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of tool names
    tool_arguments: Mapped[str] = mapped_column(Text, default="[]")  # JSON list, one entry per tool call
    tool_results: Mapped[str] = mapped_column(Text, default="[]")  # JSON list, one entry per tool call
    approval_status: Mapped[str] = mapped_column(String, default="not_required")
    error: Mapped[str] = mapped_column(Text, default="")
    start_time: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    end_time: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    duration_seconds: Mapped[float] = mapped_column(default=0.0)
    final_outcome: Mapped[str] = mapped_column(String, default="")  # "answered", "error", "awaiting_approval"
