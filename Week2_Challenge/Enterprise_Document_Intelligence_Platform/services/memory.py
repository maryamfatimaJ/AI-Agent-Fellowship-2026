"""
services/memory.py
-------------------
Keeps track of conversations so the app can remember what was said
earlier, support multiple separate chat threads (like "New Chat" in
most AI apps), and let users export, clear, or delete them.

Public functions:

    create_conversation()          -> starts a new, empty conversation thread
    conversation_exists()          -> checks if a conversation_id is valid
    add_message_to_memory()        -> saves one message into a conversation
    get_conversation_history()     -> returns all messages in a conversation
    list_conversations_for_session() -> lists a browser's conversation threads
    delete_conversation()          -> permanently removes a conversation
    clear_conversation_memory()    -> empties a conversation's messages
    get_total_conversation_count() -> counts all conversation threads
    export_conversation_as_text()  -> formats history into a readable .txt
    export_conversation_as_pdf()   -> formats history into a downloadable PDF

Storage note: everything is kept in a plain Python dictionary in memory.
This is simple and fast, but it means conversations are lost if the
Flask server restarts. That's fine for now — swap this for a real
database later if you need conversations to survive restarts.
"""

import uuid
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


# ============================================================
# CONFIGURATION
# ============================================================

# Only keep the most recent N messages per conversation, so memory
# doesn't grow forever and old context doesn't crowd the AI prompt.
MAX_MESSAGES_PER_CONVERSATION = 20

# How many characters of the first message to use as a conversation's
# auto-generated title (like "Summarize the key risks…").
TITLE_MAX_LENGTH = 40


# ============================================================
# STORAGE
# ============================================================

# Structure looks like:
# {
#   "conversation-id-1": {
#       "session_id": "browser-session-id",
#       "title": "Summarize the key risks…",
#       "messages": [ {"role": "user", "message": "...", "timestamp": "..."}, ... ],
#       "created_at": "2026-07-10T14:30:00",
#       "updated_at": "2026-07-10T14:32:04",
#   },
#   "conversation-id-2": { ... },
# }
_conversations = {}


# ============================================================
# PUBLIC FUNCTION: START A NEW CONVERSATION
# ============================================================

def create_conversation(session_id):
    """
    Create a brand-new, empty conversation thread for this browser
    session and return its ID. This is what the "New Chat" button calls.
    """
    conversation_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    _conversations[conversation_id] = {
        "session_id": session_id,
        "title": None,
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }

    return conversation_id


# ============================================================
# PUBLIC FUNCTION: CHECK IF A CONVERSATION EXISTS
# ============================================================

def conversation_exists(conversation_id):
    """True if this conversation_id is currently in memory."""
    return conversation_id in _conversations


# ============================================================
# PUBLIC FUNCTION: ADD A MESSAGE TO A CONVERSATION
# ============================================================

def add_message_to_memory(conversation_id, role, message):
    """
    Save one message into a conversation's history.

    role should be either "user" or "assistant". The very first user
    message in a conversation automatically becomes its title, the
    same way most chat apps name a conversation after what you first asked.
    """
    if conversation_id not in _conversations:
        return

    conversation = _conversations[conversation_id]

    new_entry = {
        "role": role,
        "message": message,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    conversation["messages"].append(new_entry)
    conversation["updated_at"] = datetime.now().isoformat()

    if conversation["title"] is None and role == "user":
        conversation["title"] = generate_title_from_message(message)

    trim_conversation_to_limit(conversation_id)


# ============================================================
# PRIVATE HELPER: BUILD A SHORT TITLE FROM THE FIRST MESSAGE
# ============================================================

def generate_title_from_message(message):
    """Turn the first user message into a short conversation title."""
    title = message.strip()

    if len(title) > TITLE_MAX_LENGTH:
        title = title[:TITLE_MAX_LENGTH].rstrip() + "…"

    return title


# ============================================================
# PRIVATE HELPER: KEEP ONLY THE MOST RECENT MESSAGES
# ============================================================

def trim_conversation_to_limit(conversation_id):
    """
    If a conversation's history has grown past the limit, drop the
    oldest messages so it only keeps the most recent ones.
    """
    messages = _conversations[conversation_id]["messages"]

    if len(messages) > MAX_MESSAGES_PER_CONVERSATION:
        _conversations[conversation_id]["messages"] = messages[-MAX_MESSAGES_PER_CONVERSATION:]


# ============================================================
# PUBLIC FUNCTION: GET A CONVERSATION'S HISTORY
# ============================================================

def get_conversation_history(conversation_id):
    """
    Return the list of messages in a conversation, oldest first.
    Returns an empty list if the conversation doesn't exist.
    """
    if conversation_id not in _conversations:
        return []

    return _conversations[conversation_id]["messages"]


# ============================================================
# PUBLIC FUNCTION: LIST A SESSION'S CONVERSATIONS
# ============================================================

def list_conversations_for_session(session_id):
    """
    Return every conversation thread belonging to this browser session,
    newest first — the data the "Conversations" sidebar view needs.
    """
    matches = []

    for conversation_id, conversation in _conversations.items():
        if conversation["session_id"] != session_id:
            continue

        matches.append({
            "conversation_id": conversation_id,
            "title": conversation["title"] or "New conversation",
            "message_count": len(conversation["messages"]),
            "updated_at": conversation["updated_at"],
        })

    matches.sort(key=get_updated_at_sort_key, reverse=True)
    return matches


def get_updated_at_sort_key(conversation_summary):
    """Sort helper: newest-updated conversations first."""
    return conversation_summary["updated_at"]


# ============================================================
# PUBLIC FUNCTION: DELETE A CONVERSATION
# ============================================================

def delete_conversation(conversation_id):
    """
    Permanently remove a conversation thread.
    Returns True if it existed and was deleted, False otherwise.
    """
    if conversation_id not in _conversations:
        return False

    del _conversations[conversation_id]
    return True


# ============================================================
# PUBLIC FUNCTION: COUNT TOTAL CONVERSATIONS
# ============================================================

def get_total_conversation_count():
    """Return how many conversation threads currently exist, in total."""
    return len(_conversations)


# ============================================================
# PUBLIC FUNCTION: CLEAR A CONVERSATION'S MESSAGES
# ============================================================

def clear_conversation_memory(conversation_id):
    """
    Empty out a conversation's messages and reset its title, without
    deleting the conversation thread itself. Used by the "Clear memory"
    button, which wipes the CURRENT chat's context but keeps you in it —
    different from deleting a conversation entirely from the list.
    """
    if conversation_id in _conversations:
        _conversations[conversation_id]["messages"] = []
        _conversations[conversation_id]["title"] = None


# ============================================================
# PUBLIC FUNCTION: FORMAT A CONVERSATION FOR TEXT EXPORT
# ============================================================

def export_conversation_as_text(history):
    """
    Turn a list of message dictionaries into a clean, readable block of
    text, suitable for downloading as a .txt file.

    Example output:

        [2026-07-10 14:32:01] USER: What are the key risks?
        [2026-07-10 14:32:04] ASSISTANT: Based on the documents, ...
    """
    lines = []

    for entry in history:
        role_label = entry["role"].upper()
        line = "[" + entry["timestamp"] + "] " + role_label + ": " + entry["message"]
        lines.append(line)

    conversation_text = "\n\n".join(lines)
    return conversation_text


# ============================================================
# PUBLIC FUNCTION: EXPORT A CONVERSATION AS A PDF
# ============================================================

def export_conversation_as_pdf(history):
    """
    Turn a list of message dictionaries into a downloadable PDF file.
    Returns an in-memory file (BytesIO) ready to hand to Flask's
    send_file — nothing is written to disk.
    """
    pdf_buffer = BytesIO()
    document = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Conversation Export", styles["Title"]))
    story.append(Spacer(1, 16))

    for entry in history:
        role_label = entry["role"].upper()

        # Escape HTML-sensitive characters, since reportlab's Paragraph
        # interprets a small set of tags in its text.
        safe_message = (
            entry["message"]
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        line = "<b>[" + entry["timestamp"] + "] " + role_label + ":</b> " + safe_message
        story.append(Paragraph(line, styles["Normal"]))
        story.append(Spacer(1, 10))

    document.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer