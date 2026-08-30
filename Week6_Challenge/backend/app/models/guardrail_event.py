import enum

from sqlalchemy import Boolean, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, generate_uuid


class GuardrailDirection(str, enum.Enum):
    INPUT = "input"
    OUTPUT = "output"


class GuardrailAction(str, enum.Enum):
    BLOCKED = "blocked"
    FLAGGED = "flagged"
    SANITIZED = "sanitized"
    APPROVED = "approved"


class GuardrailEvent(Base, TimestampMixin):
    __tablename__ = "guardrail_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), index=True, nullable=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    message_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="SET NULL"), index=True, nullable=True
    )
    direction: Mapped[GuardrailDirection] = mapped_column(Enum(GuardrailDirection), nullable=False)
    guardrail_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    action: Mapped[GuardrailAction] = mapped_column(Enum(GuardrailAction), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PendingActionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PendingAction(Base, TimestampMixin):
    __tablename__ = "pending_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    requested_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_args: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[PendingActionStatus] = mapped_column(
        Enum(PendingActionStatus), default=PendingActionStatus.PENDING, nullable=False, index=True
    )
    decided_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
