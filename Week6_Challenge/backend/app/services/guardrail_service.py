import logging

from sqlalchemy.orm import Session

from app.core.events import GUARDRAIL_TRIGGERED, log_event
from app.models.guardrail_event import GuardrailAction, GuardrailDirection, GuardrailEvent

logger = logging.getLogger("app.guardrails")


def record_guardrail_event(
    db: Session,
    *,
    direction: GuardrailDirection,
    guardrail_type: str,
    triggered: bool,
    action: GuardrailAction,
    workspace_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    detail: dict | None = None,
) -> GuardrailEvent:
    event = GuardrailEvent(
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        message_id=message_id,
        direction=direction,
        guardrail_type=guardrail_type,
        triggered=triggered,
        action=action,
        detail=detail,
    )
    db.add(event)
    db.commit()
    if triggered:
        log_event(
            logger,
            GUARDRAIL_TRIGGERED,
            level=logging.WARNING,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            direction=direction.value,
            guardrail_type=guardrail_type,
            action=action.value,
        )
    return event
