"""
tools/email_tools.py
------------------------
Bonus tool: Draft Follow-up Email. Uses the LLM to draft a subject and
body, since composing readable prose from context genuinely needs
language understanding — same reasoning as extract_meeting_actions in
tools/planning_tools.py. There is no real email-sending infrastructure
in this app (no SMTP config), so this tool drafts and simulates the
send; it does not actually deliver anything.
"""

from pydantic import ValidationError

from database import repository
from services.llm_service import generate_json, LLMError, LLMQuotaExceededError
from tools.task_tools import ToolError
from tools.logging_setup import get_tool_logger
from schemas import DraftFollowUpEmailInput, DraftFollowUpEmailOutput

logger = get_tool_logger("email_tools")


# ============================================================
# BONUS TOOL: DRAFT FOLLOW-UP EMAIL
# ============================================================

DRAFT_FOLLOW_UP_EMAIL_REQUIRES_APPROVAL = True  # Requirement 7: sending/simulating an email requires approval

_DRAFT_PROMPT_TEMPLATE = """Draft a short, professional follow-up email.

Recipient: {recipient}
What this follow-up is about: {context}
{task_context}

Reply with ONLY a JSON object (no markdown fences, no other text) with exactly these fields:
- "subject": a short email subject line
- "body": the email body text, written in a professional but friendly tone

Do not invent facts beyond what's given above.
"""


def draft_follow_up_email(data: DraftFollowUpEmailInput) -> DraftFollowUpEmailOutput:
    """
    Ask the LLM to draft a follow-up email's subject and body from the
    given context, optionally pulling in a related task's title and
    description for extra detail.
    """
    logger.info("draft_follow_up_email called: recipient=%r task_id=%s", data.recipient, data.task_id)

    task_context = ""
    if data.task_id:
        task = repository.get_task(data.task_id)
        if task is not None:
            task_context = f"Related task: {task.title} - {task.description}"

    prompt = _DRAFT_PROMPT_TEMPLATE.format(
        recipient=data.recipient, context=data.context, task_context=task_context
    )

    try:
        raw_result = generate_json(prompt)
    except LLMQuotaExceededError:
        # Let this propagate as-is (not wrapped in ToolError) so
        # execute_tool_with_limits (agent/nodes.py) can recognize it and
        # skip retrying an already-exhausted daily quota.
        logger.error("draft_follow_up_email failed: Gemini quota exceeded")
        raise
    except LLMError as error:
        logger.error("draft_follow_up_email failed: LLM error: %s", error)
        raise ToolError(str(error)) from error

    try:
        result = DraftFollowUpEmailOutput.model_validate({**raw_result, "recipient": data.recipient})
        logger.info("draft_follow_up_email succeeded: recipient=%s subject=%r", data.recipient, result.subject)
        return result
    except ValidationError as error:
        logger.error("draft_follow_up_email failed: invalid model response: %s", error)
        raise ToolError(
            "The language model's response didn't match the expected structure: " + str(error)
        ) from error
