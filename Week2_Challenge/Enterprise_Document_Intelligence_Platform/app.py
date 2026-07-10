"""
app.py
------
Main Flask application for the Enterprise Document Intelligence Platform.

This file ONLY handles web requests (routes). It does not contain any
document processing, embedding, or AI logic itself — that heavy lifting
lives in the services/ folder:

    services/processor.py  -> reads files and splits them into chunks
    services/rag.py         -> stores chunks in ChromaDB and talks to Gemini
    services/memory.py      -> remembers past messages in a conversation

Keeping routes short and calling helper functions makes the app easy to
read, easy to test, and easy to extend later.
"""

import os
import uuid
from flask import Flask, render_template, request, jsonify, session, Response, send_file
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load variables from the .env file (like GEMINI_API_KEY and SECRET_KEY)
# into the environment. This MUST happen before we import anything from
# services/, because services/rag.py reads GEMINI_API_KEY the moment it's
# imported, not later when a route is actually called.
load_dotenv()

# Helper functions from our services folder.
# (These are built out in later steps — for now, this app.py assumes
# they exist with these names and this behavior.)
from services.processor import extract_text_from_file, split_text_into_chunks
from services.rag import (
    add_document_to_index,
    delete_document_from_index,
    refresh_all_embeddings,
    get_answer_for_question,
    list_indexed_documents,
    get_index_stats,
    reprocess_single_document,
    find_uploaded_file_path,
    EMBEDDING_MODEL_NAME,
    GENERATION_MODEL_NAME,
    GeminiUnavailableError,
)
from services.memory import (
    add_message_to_memory,
    get_conversation_history,
    export_conversation_as_text,
    export_conversation_as_pdf,
    get_total_conversation_count,
    clear_conversation_memory,
    create_conversation,
    conversation_exists,
    list_conversations_for_session,
    delete_conversation,
)
from services.activity import log_activity, get_recent_activity, delete_activity, clear_activity


# ============================================================
# APP SETUP
# ============================================================

app = Flask(__name__)

# Needed so Flask can use sessions (to keep a simple conversation ID per user).
# In production, set this from an environment variable instead of hardcoding it.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

# Where uploaded files get saved on disk.
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Only these file types are allowed to be uploaded.
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md"}

# Make sure the uploads folder actually exists before we try to save files into it.
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# SMALL HELPER FUNCTIONS (used only inside this file)
# ============================================================

def is_allowed_file(filename):
    """Check that the uploaded file has one of our allowed extensions."""
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def get_session_id():
    """
    Every visitor gets a simple session ID stored in a cookie, so we can
    tell "their" conversations apart without needing user accounts.
    """
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


def get_active_conversation_id():
    """
    Return the current conversation thread's ID, or None if this browser
    doesn't have one active yet. Does NOT create one — used by routes
    that should show "empty" instead of silently starting a new chat.
    """
    conversation_id = session.get("conversation_id")

    if conversation_id and conversation_exists(conversation_id):
        return conversation_id

    return None


def ensure_active_conversation():
    """
    Return the current conversation thread's ID, creating a new one if
    this browser doesn't have one yet (or its old one is gone). Used by
    the /chat route, since sending a message is what should start a
    conversation if none exists.
    """
    conversation_id = get_active_conversation_id()

    if conversation_id is None:
        conversation_id = create_conversation(get_session_id())
        session["conversation_id"] = conversation_id

    return conversation_id


# ============================================================
# ROUTE: HOME PAGE
# ============================================================

@app.route("/")
def home():
    """Render the main single-page app (index.html)."""
    return render_template("index.html")


# ============================================================
# ROUTE: UPLOAD A DOCUMENT
# ============================================================

@app.route("/upload", methods=["POST"])
def upload_document():
    """
    Handle a file upload from the frontend.

    Steps:
    1. Validate that a file was actually sent, and that its type is allowed.
    2. Save the file to the uploads/ folder with a safe, unique filename.
    3. Extract its text and split it into chunks (services/processor.py).
    4. Add those chunks to the vector index so it can be searched (services/rag.py).
    """
    uploaded_file = request.files.get("file")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"error": "No file was uploaded."}), 400

    if not is_allowed_file(uploaded_file.filename):
        return jsonify({"error": "Only PDF, DOCX, TXT, and Markdown files are allowed."}), 400

    # Give the file a unique name so two uploads with the same filename
    # don't overwrite each other.
    original_name = secure_filename(uploaded_file.filename)
    document_id = str(uuid.uuid4())
    stored_filename = document_id + "_" + original_name
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)

    uploaded_file.save(file_path)

    # Hand the actual document processing off to our services.
    document_text = extract_text_from_file(file_path)
    text_chunks = split_text_into_chunks(document_text)

    try:
        add_document_to_index(document_id, original_name, text_chunks)
    except GeminiUnavailableError as error:
        os.remove(file_path)  # don't leave an unindexed orphan file behind
        return jsonify({"error": str(error)}), 503

    log_activity("upload", "Uploaded \"" + original_name + "\"")

    return jsonify({
        "message": "File uploaded and indexed successfully.",
        "document_id": document_id,
        "filename": original_name,
    }), 200


# ============================================================
# ROUTE: LIST ALL DOCUMENTS
# ============================================================

@app.route("/documents", methods=["GET"])
def list_documents():
    """
    Return every currently indexed document, with its chunk count and
    file size, so the frontend's document library reflects what's
    actually in ChromaDB instead of showing placeholder data.
    """
    documents = list_indexed_documents()

    for document in documents:
        file_path = find_uploaded_file_path(document["document_id"])
        document["size_bytes"] = os.path.getsize(file_path) if file_path else 0

    return jsonify({"documents": documents}), 200


# ============================================================
# ROUTE: VIEW/OPEN AN UPLOADED DOCUMENT
# ============================================================

@app.route("/view/<document_id>", methods=["GET"])
def view_document(document_id):
    """
    Serve the original uploaded file so it can be opened in a new browser
    tab. PDFs and text files preview directly; DOCX files download,
    since browsers don't render Word documents natively.
    """
    file_path = find_uploaded_file_path(document_id)

    if file_path is None:
        return jsonify({"error": "Document not found."}), 404

    original_name = os.path.basename(file_path).partition("_")[2]

    return send_file(file_path, as_attachment=False, download_name=original_name)


# ============================================================
# ROUTE: DASHBOARD STATISTICS
# ============================================================

@app.route("/stats", methods=["GET"])
def get_stats():
    """
    Return the numbers the dashboard's statistics cards and storage bar
    need: how many documents/chunks are indexed, how many conversations
    exist, and how much disk space uploads are using.
    """
    index_stats = get_index_stats()

    storage_used_bytes = 0
    for stored_filename in os.listdir(app.config["UPLOAD_FOLDER"]):
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)
        storage_used_bytes += os.path.getsize(file_path)

    return jsonify({
        "total_documents": index_stats["total_documents"],
        "total_chunks": index_stats["total_chunks"],
        "total_conversations": get_total_conversation_count(),
        "storage_used_bytes": storage_used_bytes,
    }), 200


# ============================================================
# ROUTE: CHAT WITH THE DOCUMENTS
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():
    """
    Handle a chat message from the user.

    Steps:
    1. Read the user's question from the request body.
    2. Ask services/rag.py to find relevant chunks and generate an answer.
    3. Save both the question and the answer into conversation memory.
    4. Return the answer (plus its sources) as JSON.
    """
    data = request.get_json()
    question = data.get("question", "").strip() if data else ""

    if question == "":
        return jsonify({"error": "Question cannot be empty."}), 400

    conversation_id = ensure_active_conversation()

    # rag.py is expected to return a dictionary like:
    # {"answer": "...", "sources": [ {...}, {...} ]}
    try:
        result = get_answer_for_question(question, conversation_id)
    except GeminiUnavailableError as error:
        return jsonify({"error": str(error)}), 503

    # Keep track of this exchange so future questions have context.
    add_message_to_memory(conversation_id, role="user", message=question)
    add_message_to_memory(conversation_id, role="assistant", message=result["answer"])
    log_activity("chat", "Asked: \"" + question[:60] + "\"")

    return jsonify({
        "answer": result["answer"],
        "sources": result.get("sources", []),
    }), 200


# ============================================================
# ROUTE: DELETE A DOCUMENT
# ============================================================

@app.route("/delete/<document_id>", methods=["DELETE"])
def delete_document(document_id):
    """
    Remove a document from the vector index AND delete its file from
    the uploads/ folder, so it's gone from both places at once.
    """
    # Grab the filename before deleting it, so we can log a readable message.
    file_path = find_uploaded_file_path(document_id)
    filename_for_log = os.path.basename(file_path).partition("_")[2] if file_path else document_id

    was_deleted = delete_document_from_index(document_id)

    if not was_deleted:
        return jsonify({"error": "Document not found."}), 404

    if file_path:
        os.remove(file_path)

    log_activity("delete", "Deleted \"" + filename_for_log + "\"")

    return jsonify({"message": "Document deleted successfully."}), 200


# ============================================================
# ROUTE: REPROCESS ONE DOCUMENT
# ============================================================

@app.route("/reprocess/<document_id>", methods=["POST"])
def reprocess_document(document_id):
    """Re-extract and re-chunk a single document, without touching the rest."""
    try:
        was_reprocessed = reprocess_single_document(document_id)
    except GeminiUnavailableError as error:
        return jsonify({"error": str(error)}), 503

    if not was_reprocessed:
        return jsonify({"error": "Document file not found on disk."}), 404

    log_activity("reprocess", "Reprocessed a document")

    return jsonify({"message": "Document reprocessed successfully."}), 200


# ============================================================
# ROUTE: CLEAR CONVERSATION MEMORY
# ============================================================

@app.route("/clear-memory", methods=["POST"])
def clear_memory():
    """Wipe the current conversation's messages, keeping the thread active."""
    conversation_id = get_active_conversation_id()

    if conversation_id:
        clear_conversation_memory(conversation_id)

    return jsonify({"message": "Memory cleared."}), 200


# ============================================================
# ROUTE: CONVERSATION MEMORY STATUS
# ============================================================

@app.route("/memory", methods=["GET"])
def get_memory_status():
    """
    Return how much conversation memory the active thread has used, so
    the "Conversation Memory" panel can show real numbers. Doesn't
    create a conversation just to check this — a fresh visitor with no
    chat yet correctly sees zero, not a phantom empty conversation.
    """
    conversation_id = get_active_conversation_id()
    history = get_conversation_history(conversation_id) if conversation_id else []

    return jsonify({
        "message_count": len(history),
        "max_messages": 20,
    }), 200


# ============================================================
# ROUTE: START A NEW CONVERSATION
# ============================================================

@app.route("/conversations/new", methods=["POST"])
def start_new_conversation():
    """
    Create a brand-new, empty conversation thread and make it the
    active one — this is what the "New Chat" button calls.
    """
    conversation_id = create_conversation(get_session_id())
    session["conversation_id"] = conversation_id

    return jsonify({"conversation_id": conversation_id}), 200


# ============================================================
# ROUTE: LIST THIS BROWSER'S CONVERSATIONS
# ============================================================

@app.route("/conversations", methods=["GET"])
def list_conversations():
    """Return every conversation thread this browser has started."""
    conversations = list_conversations_for_session(get_session_id())
    active_conversation_id = get_active_conversation_id()

    for conversation in conversations:
        conversation["is_active"] = conversation["conversation_id"] == active_conversation_id

    return jsonify({"conversations": conversations}), 200


# ============================================================
# ROUTE: LOAD (AND SWITCH TO) A CONVERSATION
# ============================================================

@app.route("/conversations/<conversation_id>", methods=["GET"])
def load_conversation(conversation_id):
    """
    Return one conversation's messages, and make it the active thread —
    so sending a new message afterward continues THIS conversation.
    """
    if not conversation_exists(conversation_id):
        return jsonify({"error": "Conversation not found."}), 404

    session["conversation_id"] = conversation_id
    history = get_conversation_history(conversation_id)

    return jsonify({"conversation_id": conversation_id, "messages": history}), 200


# ============================================================
# ROUTE: DELETE A CONVERSATION
# ============================================================

@app.route("/conversations/<conversation_id>", methods=["DELETE"])
def remove_conversation(conversation_id):
    """
    Permanently delete a conversation thread. If it was the active one,
    the browser is left with no active conversation — the next message
    sent will start a fresh one.
    """
    was_deleted = delete_conversation(conversation_id)

    if not was_deleted:
        return jsonify({"error": "Conversation not found."}), 404

    if session.get("conversation_id") == conversation_id:
        session.pop("conversation_id", None)

    return jsonify({"message": "Conversation deleted."}), 200


# ============================================================
# ROUTE: RECENT ACTIVITY
# ============================================================

@app.route("/activity", methods=["GET"])
def get_activity():
    """Return the most recent actions taken across the workspace."""
    return jsonify({"activity": get_recent_activity()}), 200


# ============================================================
# ROUTE: DELETE ONE ACTIVITY ENTRY
# ============================================================

@app.route("/activity/<activity_id>", methods=["DELETE"])
def remove_activity(activity_id):
    """Remove a single entry from the Recent Activity feed."""
    was_deleted = delete_activity(activity_id)

    if not was_deleted:
        return jsonify({"error": "Activity entry not found."}), 404

    return jsonify({"message": "Activity entry deleted."}), 200


# ============================================================
# ROUTE: CLEAR ALL ACTIVITY
# ============================================================

@app.route("/activity", methods=["DELETE"])
def clear_activity_route():
    """Remove every entry from the Recent Activity feed at once."""
    clear_activity()
    return jsonify({"message": "Activity cleared."}), 200


# ============================================================
# ROUTE: REFRESH EMBEDDINGS
# ============================================================

@app.route("/refresh", methods=["POST"])
def refresh_embeddings():
    """
    Re-process every uploaded document and rebuild the vector index.
    Useful if you change chunking settings or the embedding model.
    """
    try:
        total_documents_refreshed = refresh_all_embeddings()
    except GeminiUnavailableError as error:
        return jsonify({"error": str(error)}), 503

    return jsonify({
        "message": "Embeddings refreshed successfully.",
        "documents_refreshed": total_documents_refreshed,
    }), 200


# ============================================================
# ROUTE: EXPORT CONVERSATION
# ============================================================

@app.route("/export", methods=["GET"])
def export_conversation():
    """
    Let the user download their current conversation as a plain text file.
    """
    conversation_id = get_active_conversation_id()
    history = get_conversation_history(conversation_id) if conversation_id else []

    if not history:
        return jsonify({"error": "No conversation to export yet."}), 400

    conversation_text = export_conversation_as_text(history)

    # Send the text back as a downloadable .txt file instead of JSON.
    return Response(
        conversation_text,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=conversation.txt"},
    )


# ============================================================
# ROUTE: EXPORT CONVERSATION AS PDF
# ============================================================

@app.route("/export-pdf", methods=["GET"])
def export_conversation_pdf():
    """Let the user download their current conversation as a PDF file."""
    conversation_id = get_active_conversation_id()
    history = get_conversation_history(conversation_id) if conversation_id else []

    if not history:
        return jsonify({"error": "No conversation to export yet."}), 400

    pdf_buffer = export_conversation_as_pdf(history)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="conversation.pdf",
    )


# ============================================================
# ROUTE: SETTINGS (READ-ONLY AI CONFIGURATION)
# ============================================================

@app.route("/settings", methods=["GET"])
def get_settings():
    """
    Return the actual AI models and vector database this app is
    configured to use, read directly from services/rag.py — so the
    Settings page always reflects reality instead of static text.
    """
    return jsonify({
        "embedding_model": EMBEDDING_MODEL_NAME,
        "llm_provider": "Google Gemini (" + GENERATION_MODEL_NAME + ")",
        "vector_database": "ChromaDB (local, persistent)",
    }), 200


# ============================================================
# RUN THE APP
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)