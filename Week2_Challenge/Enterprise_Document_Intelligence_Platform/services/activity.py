"""
services/activity.py
---------------------
Keeps a short, shared log of recent actions (uploads, deletes,
reprocessing, questions asked) so the dashboard's "Recent Activity"
panel has something real to show.

This log is shared across all visitors (not per-session), since it's
meant to reflect what's happening in the workspace as a whole — similar
to an activity feed.

Public functions:

    log_activity()        -> records one event
    get_recent_activity() -> returns the most recent events, newest first
    delete_activity()     -> removes one event by its ID
    clear_activity()      -> removes every event at once
"""

import uuid
from datetime import datetime


# Only keep this many events in memory, so the log doesn't grow forever.
MAX_ACTIVITY_ENTRIES = 20

# Newest entries are kept at the front of this list.
_activity_log = []


# ============================================================
# PUBLIC FUNCTION: RECORD ONE EVENT
# ============================================================

def log_activity(event_type, text):
    """
    Add one entry to the activity log.

    event_type should be one of: "upload", "delete", "reprocess", "chat"
    (the frontend uses this to color-code the timeline dot).
    """
    entry = {
        "id": str(uuid.uuid4()),
        "event_type": event_type,
        "text": text,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    _activity_log.insert(0, entry)

    if len(_activity_log) > MAX_ACTIVITY_ENTRIES:
        _activity_log.pop()


# ============================================================
# PUBLIC FUNCTION: GET RECENT EVENTS
# ============================================================

def get_recent_activity(limit=10):
    """Return the most recent events, newest first."""
    return _activity_log[:limit]


# ============================================================
# PUBLIC FUNCTION: DELETE ONE EVENT
# ============================================================

def delete_activity(activity_id):
    """
    Remove one entry from the activity log by its ID.
    Returns True if it was found and removed, False otherwise.
    """
    for index, entry in enumerate(_activity_log):
        if entry["id"] == activity_id:
            _activity_log.pop(index)
            return True

    return False


# ============================================================
# PUBLIC FUNCTION: CLEAR THE WHOLE LOG
# ============================================================

def clear_activity():
    """Remove every entry from the activity log at once."""
    _activity_log.clear()