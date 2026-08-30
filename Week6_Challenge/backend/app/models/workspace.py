from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, generate_uuid


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped["User"] = relationship(back_populates="workspaces")
    assistants: Mapped[list["Assistant"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    prompt_templates: Mapped[list["PromptTemplate"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    skills: Mapped[list["Skill"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    memories: Mapped[list["Memory"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    settings: Mapped["WorkspaceSettings"] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", uselist=False
    )
