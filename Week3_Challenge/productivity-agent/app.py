"""
app.py
------
Flask entry point. This file ONLY handles web requests — it never
contains agent decision logic, tool code, or database queries directly.
Those live in agent/, tools/, and database/ once those phases are built.
"""

import os
import uuid
import io
from flask import Flask, render_template, request, jsonify, session, send_file
from pydantic import ValidationError
from config import settings

app = Flask(__name__)

# Fail fast with a clear message if required config is missing,
# instead of crashing deep inside an LLM call later (Requirement 8).
try:
    settings.validate()
except RuntimeError as error:
    print("STARTUP ERROR:", error)
    raise

app.secret_key = settings.SECRET_KEY

# Create database tables if they don't exist yet.
from database.repository import init_db
init_db()


def get_session_id():
    """Give each browser session a simple ID, so runs can be told apart later."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


@app.route("/")
def home():
    """Render the main single-page app."""
    return render_template("index.html")


from agent.graph import run_agent
from database.repository import list_execution_logs
from database import repository
from schemas import TaskCreate, TaskUpdate, NoteCreate, NoteUpdate


def _agent_result_to_response(result):
    """
    Turn an AgentResult into the JSON shape the frontend already expects
    (it was designed around this shape back in Phase 1, before the real
    agent existed, specifically so this wiring step wouldn't need any
    frontend changes).
    """
    steps_payload = [
        {"stage": step.stage, "detail": step.detail}
        for step in result.steps
    ]

    if result.error:
        return {"error": result.error, "steps": steps_payload, "approval_request": None}, 400

    if result.pending_approval:
        approval = result.pending_approval
        return {
            "reply": None,
            "steps": steps_payload,
            "approval_request": {
                "tool_name": approval.tool_name,
                "title": approval.title,
                "description": approval.description,
                "arguments": {key: str(value) for key, value in approval.tool_arguments.items()},
            },
        }, 200

    return {"reply": result.final_response, "steps": steps_payload, "approval_request": None}, 200


@app.route("/chat", methods=["POST"])
def chat():
    """Handle a chat message from the user by running the real agent controller."""
    data = request.get_json()
    message = data.get("message", "").strip() if data else ""

    if message == "":
        return jsonify({"error": "Message cannot be empty."}), 400

    try:
        result = run_agent(message, get_session_id())
    except Exception as error:
        # Final safety net: anything truly unexpected (not one of the
        # specific cases already handled inside run_agent) is caught
        # here so the user gets a clean message instead of a raw
        # stack trace (Requirement 8). Details go to the server
        # console only, never to the client.
        print("Unexpected error in /chat:", error)
        return jsonify({"error": "Something went wrong processing your request. Please try again."}), 500

    if result.pending_approval:
        # Remember what was proposed and what the original request was,
        # so /approve or /reject can resume this exact run later.
        session["pending_user_request"] = message
        session["pending_tool_name"] = result.pending_approval.tool_name
        session["pending_tool_arguments"] = result.pending_approval.tool_arguments

    payload, status_code = _agent_result_to_response(result)
    return jsonify(payload), status_code


@app.route("/approve", methods=["POST"])
def approve():
    """Resume a run after the user approves the proposed action."""
    pending_request = session.get("pending_user_request")
    pending_tool_name = session.get("pending_tool_name")
    pending_tool_arguments = session.get("pending_tool_arguments")

    if not pending_request or not pending_tool_name:
        return jsonify({"error": "There's no pending action to approve."}), 400

    session.pop("pending_user_request", None)
    session.pop("pending_tool_name", None)
    session.pop("pending_tool_arguments", None)

    try:
        result = run_agent(
            pending_request,
            get_session_id(),
            already_approved={"tool_name": pending_tool_name, "tool_arguments": pending_tool_arguments},
        )
    except Exception as error:
        print("Unexpected error in /approve:", error)
        return jsonify({"error": "Something went wrong running that action. Please try again."}), 500

    payload, status_code = _agent_result_to_response(result)
    return jsonify(payload), status_code


@app.route("/reject", methods=["POST"])
def reject():
    """Discard a pending action without running it, per Requirement 7."""
    session.pop("pending_user_request", None)
    session.pop("pending_tool_name", None)
    session.pop("pending_tool_arguments", None)

    return jsonify({
        "reply": "Rejected. Nothing was changed.",
        "steps": [{"stage": "done", "detail": "Action rejected by the user."}],
        "approval_request": None,
    }), 200


@app.route("/logs", methods=["GET"])
def get_logs():
    """Return the most recent execution logs, for the Execution History page."""
    logs = list_execution_logs()

    return jsonify({
        "logs": [
            {
                "run_id": log.run_id,
                "user_request": log.user_request,
                "final_outcome": log.final_outcome,
                "approval_status": log.approval_status,
                "tools_called": log.tools_called,
                "error": log.error,
                "start_time": log.start_time.isoformat(),
                "duration_seconds": round(log.duration_seconds, 2),
            }
            for log in logs
        ]
    }), 200


def _task_to_json(task):
    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority.value,
        "status": task.status.value,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "created_date": task.created_date.isoformat(),
        "updated_date": task.updated_date.isoformat(),
        "tags": task.tags,
        "source": task.source,
        "notes": task.notes,
    }


def _note_to_json(note):
    return {
        "note_id": note.note_id,
        "title": note.title,
        "content": note.content,
        "category": note.category,
        "tags": note.tags,
        "created_date": note.created_date.isoformat(),
        "updated_date": note.updated_date.isoformat(),
    }


@app.route("/tasks", methods=["GET"])
def get_tasks():
    """Return every task, for the Tasks board."""
    tasks = repository.list_tasks()
    return jsonify({"tasks": [_task_to_json(task) for task in tasks]}), 200


@app.route("/tasks", methods=["POST"])
def create_task():
    """
    Create a new task directly from the Tasks board.

    This writes immediately and does NOT go through the agent's approval
    flow — that flow still exists separately for tasks the agent proposes
    in chat. Direct board edits are a deliberate second write-path, by
    explicit choice, since a user editing their own board is not the same
    risk profile as an autonomous agent acting on their behalf.
    """
    data = request.get_json() or {}
    try:
        task_in = TaskCreate(**data)
    except ValidationError as error:
        return jsonify({"error": _validation_error_message(error)}), 400

    task = repository.create_task(task_in)
    return jsonify(_task_to_json(task)), 201


@app.route("/tasks/<task_id>", methods=["PATCH"])
def update_task_route(task_id):
    """Update fields on an existing task directly from the Tasks board."""
    data = request.get_json() or {}
    data.pop("task_id", None)
    try:
        task_in = TaskUpdate(task_id=task_id, **data)
    except ValidationError as error:
        return jsonify({"error": _validation_error_message(error)}), 400

    task = repository.update_task(task_id, task_in)
    if task is None:
        return jsonify({"error": f"No task found with ID '{task_id}'."}), 404
    return jsonify(_task_to_json(task)), 200


@app.route("/tasks/<task_id>", methods=["DELETE"])
def delete_task_route(task_id):
    """Delete a task directly from the Tasks board."""
    deleted = repository.delete_task(task_id)
    if not deleted:
        return jsonify({"error": f"No task found with ID '{task_id}'."}), 404
    return jsonify({"task_id": task_id, "deleted": True}), 200


@app.route("/notes", methods=["GET"])
def get_notes():
    """Return every saved note, for the Notes page."""
    notes = repository.list_notes()
    return jsonify({"notes": [_note_to_json(note) for note in notes]}), 200


@app.route("/notes", methods=["POST"])
def create_note_route():
    """Create a new note directly from the Notes view."""
    data = request.get_json() or {}
    try:
        note_in = NoteCreate(**data)
    except ValidationError as error:
        return jsonify({"error": _validation_error_message(error)}), 400

    note = repository.create_note(note_in)
    return jsonify(_note_to_json(note)), 201


@app.route("/notes/<note_id>", methods=["PATCH"])
def update_note_route(note_id):
    """Update fields on an existing note directly from the Notes view."""
    data = request.get_json() or {}
    data.pop("note_id", None)
    try:
        note_in = NoteUpdate(note_id=note_id, **data)
    except ValidationError as error:
        return jsonify({"error": _validation_error_message(error)}), 400

    note = repository.update_note(note_id, note_in)
    if note is None:
        return jsonify({"error": f"No note found with ID '{note_id}'."}), 404
    return jsonify(_note_to_json(note)), 200


@app.route("/notes/<note_id>", methods=["DELETE"])
def delete_note_route(note_id):
    """Delete a note directly from the Notes view."""
    deleted = repository.delete_note(note_id)
    if not deleted:
        return jsonify({"error": f"No note found with ID '{note_id}'."}), 404
    return jsonify({"note_id": note_id, "deleted": True}), 200


@app.route("/notes/search", methods=["GET"])
def search_notes_route():
    """
    Keyword search across note titles and bodies, for the Notes view's
    search bar.

    This is keyword matching only (SQL substring match) — NOT semantic
    (meaning-based) search. Semantic search would need an embeddings
    pipeline (e.g. calling an embedding model for every note and query,
    storing vectors, and comparing by cosine similarity) that doesn't
    exist anywhere in this codebase yet. Wiring that up is future work;
    this endpoint's shape won't need to change when it's added.
    """
    query_text = request.args.get("q", "").strip()
    category = request.args.get("category") or None

    if query_text == "":
        notes = repository.list_notes()
    else:
        notes = repository.search_notes(query_text, category=category)

    return jsonify({"notes": [_note_to_json(note) for note in notes]}), 200


def _validation_error_message(error: ValidationError) -> str:
    """Turn a Pydantic ValidationError into one clean, readable sentence."""
    first = error.errors()[0]
    field = ".".join(str(part) for part in first["loc"])
    return f"Invalid value for '{field}': {first['msg']}"


@app.route("/settings", methods=["GET"])
def get_settings():
    """Return the real, currently-configured model and execution limits, for the Settings page."""
    return jsonify({
        "generation_model": settings.GENERATION_MODEL,
        "max_agent_steps": settings.MAX_AGENT_STEPS,
        "max_tool_retries": settings.MAX_TOOL_RETRIES,
        "tool_timeout_seconds": settings.TOOL_TIMEOUT_SECONDS,
        "database_url": settings.DATABASE_URL,
    }), 200


@app.route("/export-chat", methods=["POST"])
def export_chat():
    """Build a simple PDF of the current conversation and send it back as a download."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from xml.sax.saxutils import escape

    data = request.get_json()
    messages = data.get("messages", []) if data else []

    if not messages:
        return jsonify({"error": "No conversation to export."}), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("Title2", parent=styles["Heading1"], fontSize=18, spaceAfter=14)
    user_style = ParagraphStyle("User2", parent=styles["Normal"], fontSize=11, spaceAfter=10, textColor="#0F766E")
    agent_style = ParagraphStyle("Agent2", parent=styles["Normal"], fontSize=11, spaceAfter=10)

    story = [Paragraph("Trace &mdash; Chat Export", title_style), Spacer(1, 6)]

    for message in messages:
        role_label = "You" if message.get("role") == "user" else "Trace"
        style = user_style if message.get("role") == "user" else agent_style
        safe_content = escape(message.get("content", "")).replace("\n", "<br/>")
        story.append(Paragraph("<b>" + role_label + ":</b> " + safe_content, style))

    doc.build(story)
    buffer.seek(0)

    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="trace-chat-export.pdf")


if __name__ == "__main__":
    app.run(debug=True)