"""Webhook endpoint for auto-triggering validation on evidence or environment changes."""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from auditly.api.operations import validate_evidence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


class WebhookEvent(BaseModel):
    """
    WebhookEvent represents the payload structure for webhook events.

    Example:
        {
            "event_type": "evidence_changed",
            "environment": "production",
            "evidence_id": "abc123",
            "payload": {"key": "value"}
        }
    """

    event_type: str = Field(
        ...,
        description="Type of event triggering the webhook (e.g., 'evidence_changed', 'environment_changed').",
        examples=["evidence_changed", "environment_changed"],
    )
    environment: str = Field(
        ...,
        description="Target environment key (e.g., 'production', 'staging').",
        examples=["production", "staging"],
    )
    evidence_id: str | None = Field(
        None,
        description="Optional evidence ID related to the event.",
        examples=["abc123"],
    )
    payload: dict | None = Field(
        None,
        description="Optional event-specific payload (arbitrary key-value data).",
        examples=[{"key": "value"}],
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def webhook_handler(event: WebhookEvent):
    """
    Handle webhook events to auto-trigger validation on evidence or environment changes.

    This endpoint is intended for integration with CI/CD pipelines, external systems, or manual triggers
    to initiate compliance validation workflows when evidence or environment state changes.

    - **event_type**: Type of event (e.g., 'evidence_changed', 'environment_changed').
    - **environment**: Target environment key (e.g., 'production').
    - **evidence_id**: Optional evidence ID if the event relates to a specific evidence item.
    - **payload**: Optional event-specific data.

    Returns HTTP 202 Accepted if the event is processed.
    """
    logger.info(f"Received webhook event: {event.event_type} for env={event.environment}")
    try:
        # For now, always trigger full validation for the environment
        _, summary = validate_evidence(
            config_path="config.yaml",
            environment=event.environment,
        )
        logger.info(f"Validation triggered by webhook: {summary}")
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Webhook validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {e}") from e
