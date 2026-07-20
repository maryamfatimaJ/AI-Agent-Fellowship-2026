"""
tools/reminder_tools.py
--------------------------
Bonus tool: Create Reminder.
"""

from database import repository
from tools.logging_setup import get_tool_logger
from schemas import ReminderCreate, ReminderOut

logger = get_tool_logger("reminder_tools")


# ============================================================
# BONUS TOOL: CREATE REMINDER
# ============================================================

CREATE_REMINDER_REQUIRES_APPROVAL = True  # Requirement 7: creating a reminder is an irreversible-ish action


def create_reminder(data: ReminderCreate) -> ReminderOut:
    """Create a new reminder and return it."""
    logger.info("create_reminder called: message=%r remind_at=%s task_id=%s", data.message, data.remind_at, data.task_id)
    reminder = repository.create_reminder(data)
    logger.info("create_reminder succeeded: reminder_id=%s", reminder.reminder_id)
    return reminder
