"""
agent/memory.py
------------------
Session memory for Requirement 11. This is deliberately NOT persisted
to the database — the requirement only asks for memory "within the
current session," so an in-memory store (lost on server restart) is
the correct amount of persistence here, not more.
"""

from dataclasses import dataclass, field

# Keep only the most recent messages, so memory doesn't grow forever
# and old context doesn't crowd out the decision prompt.
MAX_MESSAGES = 20


@dataclass
class SessionMemory:
    """Everything remembered about one browser session."""
    messages: list = field(default_factory=list)         # [{"role": "user"/"agent", "content": str}]
    last_shown_tasks: list = field(default_factory=list)  # the most recent list_tasks result, in order shown
    preferences: list = field(default_factory=list)       # short strings, e.g. "prefers morning scheduling"
    last_tool_result: dict | None = None                  # {"tool_name": str, "result": str} — the most recent
                                                           # tool call of ANY kind, so a later turn can refer back
                                                           # to it even when it wasn't a list_tasks call


# One SessionMemory per session_id. A plain dict is enough — this is
# exactly the same pattern used elsewhere in this app for in-memory,
# session-scoped state.
_session_store = {}


def get_session_memory(session_id):
    """Return this session's memory, creating a fresh one if it doesn't exist yet."""
    if session_id not in _session_store:
        _session_store[session_id] = SessionMemory()
    return _session_store[session_id]


def add_message(session_id, role, content):
    """Record one message (user or agent) and trim to the size limit."""
    memory = get_session_memory(session_id)
    memory.messages.append({"role": role, "content": content})
    if len(memory.messages) > MAX_MESSAGES:
        memory.messages = memory.messages[-MAX_MESSAGES:]


def set_last_shown_tasks(session_id, tasks):
    """
    Remember the exact list of tasks most recently shown to the user,
    in order — this is what lets a follow-up like "mark the second one
    complete" resolve to a real task_id.
    """
    memory = get_session_memory(session_id)
    memory.last_shown_tasks = tasks


def set_last_tool_result(session_id, tool_name, result):
    """
    Remember the most recent tool call and its result, regardless of
    which tool it was — this is what lets a later turn refer back to
    "that" search / plan / extraction even when it wasn't a list_tasks
    call (last_shown_tasks only covers that one specific case).
    """
    memory = get_session_memory(session_id)
    memory.last_tool_result = {"tool_name": tool_name, "result": str(result)}


def add_preference(session_id, preference_text):
    """Record a preference the user stated during this session."""
    memory = get_session_memory(session_id)
    memory.preferences.append(preference_text)


def clear_session_memory(session_id):
    """Forget everything about this session."""
    _session_store.pop(session_id, None)
