"""The tool surface available to the agent orchestrator (app/agent/orchestrator.py)
and to the pending-actions approval flow (app/api/routers/guardrails.py). Each
tool wraps an existing Week 5 capability rather than introducing new business
logic — search_documents wraps RAG retrieval, run_skill wraps the skill
engine, save_memory wraps memory upsert, delete_document wraps the existing
document-deletion behavior. Risk levels gate which tools execute immediately
vs. require human approval via a PendingAction row.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.memory.memory_service import upsert_memory
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.guardrail_event import PendingAction
from app.models.skill import Skill
from app.rag.retrieval import retrieve_relevant_chunks
from app.services.skill_service import run_skill

logger = logging.getLogger("app.agent.tools")


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolResult:
    output: Any = None
    error: str | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    risk_level: RiskLevel
    parameters: dict
    handler: Callable[..., ToolResult]


def _search_documents(args: dict, *, workspace_id: str, db: Session, **_ignored) -> ToolResult:
    query = (args or {}).get("query", "")
    if not query:
        return ToolResult(error="query is required")
    chunks = retrieve_relevant_chunks(workspace_id, query, db)
    return ToolResult(output={"results": chunks})


def _run_skill_tool(
    args: dict, *, workspace_id: str, user_id: str, db: Session, conversation: Conversation | None = None, **_ignored
) -> ToolResult:
    skill_name = (args or {}).get("skill_name", "")
    input_text = (args or {}).get("input_text", "")
    if not skill_name or not input_text:
        return ToolResult(error="skill_name and input_text are required")
    skill = db.query(Skill).filter(Skill.workspace_id == workspace_id, Skill.name == skill_name).first()
    if skill is None:
        return ToolResult(error=f"No skill named '{skill_name}' in this workspace")
    output, _user_msg, _assistant_msg = run_skill(skill, input_text, user_id, db, conversation=conversation)
    return ToolResult(output={"output": output})


def _save_memory_tool(
    args: dict, *, workspace_id: str, user_id: str, db: Session, conversation: Conversation | None = None, **_ignored
) -> ToolResult:
    key = (args or {}).get("key", "")
    value = (args or {}).get("value", "")
    if not key or not value:
        return ToolResult(error="key and value are required")
    memory = upsert_memory(
        workspace_id, user_id, key, value, db, conversation_id=conversation.id if conversation else None
    )
    return ToolResult(output={"memory_id": memory.id})


def _delete_document_tool(args: dict, *, workspace_id: str, db: Session, **_ignored) -> ToolResult:
    document_id = (args or {}).get("document_id", "")
    document = db.query(Document).filter(Document.id == document_id, Document.workspace_id == workspace_id).first()
    if document is None:
        return ToolResult(error=f"No document with id '{document_id}' in this workspace")
    filename = document.filename
    db.delete(document)
    db.commit()
    return ToolResult(output={"deleted": filename})


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_documents": ToolSpec(
        name="search_documents",
        description="Search the workspace's uploaded documents for relevant excerpts.",
        risk_level=RiskLevel.LOW,
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to search for"}},
            "required": ["query"],
        },
        handler=_search_documents,
    ),
    "run_skill": ToolSpec(
        name="run_skill",
        description="Run one of the workspace's predefined skills (e.g. Summarize, SWOT analysis) on a piece of text.",
        risk_level=RiskLevel.LOW,
        parameters={
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "Exact name of the skill to run"},
                "input_text": {"type": "string", "description": "Text to run the skill on"},
            },
            "required": ["skill_name", "input_text"],
        },
        handler=_run_skill_tool,
    ),
    "save_memory": ToolSpec(
        name="save_memory",
        description="Save a durable fact about the user for later recall.",
        risk_level=RiskLevel.MEDIUM,
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Short slug identifying the fact"},
                "value": {"type": "string", "description": "The fact, phrased plainly"},
            },
            "required": ["key", "value"],
        },
        handler=_save_memory_tool,
    ),
    "delete_document": ToolSpec(
        name="delete_document",
        description=(
            "Permanently delete an uploaded document and its indexed content. "
            "Destructive and irreversible — always requires human approval."
        ),
        risk_level=RiskLevel.HIGH,
        parameters={
            "type": "object",
            "properties": {"document_id": {"type": "string", "description": "id of the document to delete"}},
            "required": ["document_id"],
        },
        handler=_delete_document_tool,
    ),
}


def execute_tool(
    name: str,
    args: dict,
    *,
    workspace_id: str,
    user_id: str,
    db: Session,
    conversation: Conversation | None = None,
) -> ToolResult:
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        return ToolResult(error=f"Unknown tool '{name}'")
    try:
        return spec.handler(args, workspace_id=workspace_id, user_id=user_id, db=db, conversation=conversation)
    except Exception as exc:
        logger.exception("Tool '%s' raised an unexpected error", name)
        return ToolResult(error=str(exc))


def execute_approved_action(pending_action: PendingAction, db: Session) -> dict:
    """Called once a human approves a HIGH-risk pending action — actually runs
    the tool call that was deferred at proposal time."""
    result = execute_tool(
        pending_action.tool_name,
        pending_action.tool_args or {},
        workspace_id=pending_action.workspace_id,
        user_id=pending_action.requested_by,
        db=db,
        conversation=None,
    )
    return {"output": result.output, "error": result.error}
