from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.dependencies import ServiceDep
from backend.app.models.enums import IncidentSeverity, IncidentSource
from backend.app.models.schemas import ErrorResponse, WebhookResponse
from backend.app.services.incident_service import DuplicateWebhookError

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# ------------------------------------------------------------------
# PagerDuty normalizer
# ------------------------------------------------------------------


def normalize_pagerduty(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract and normalize fields from a PagerDuty webhook payload."""
    event = payload.get("event", {})
    data = event.get("data", {})

    external_event_id = payload.get("id", "") or data.get("id", "")
    title = data.get("title", "Untitled PagerDuty Incident")
    service_name = data.get("service", {})
    if isinstance(service_name, dict):
        service_name = service_name.get("summary", "unknown")

    environment = data.get("body", {})
    if isinstance(environment, dict):
        environment = environment.get("details", {}).get("environment", "production")
    else:
        environment = "production"

    body_details = data.get("body", {}).get("details", {})
    description = data.get("description", body_details.get("description", ""))
    if isinstance(description, dict):
        description = str(description)

    urgency = data.get("urgency", "high")
    severity_map = {
        "high": IncidentSeverity.SEV1,
        "medium": IncidentSeverity.SEV2,
        "low": IncidentSeverity.SEV3,
    }
    severity = severity_map.get(urgency, IncidentSeverity.SEV2)

    return {
        "external_event_id": str(external_event_id),
        "title": title,
        "severity": severity,
        "service": str(service_name),
        "environment": str(environment),
        "description": str(description),
        "stack_traces": [],
    }


# ------------------------------------------------------------------
# Sentry normalizer
# ------------------------------------------------------------------


def normalize_sentry(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract and normalize fields from a Sentry webhook payload."""
    external_event_id = payload.get("id", "") or payload.get("eventID", "")
    title = payload.get("message", payload.get("culprit", "Untitled Sentry Issue"))
    project = payload.get("project", {})
    if isinstance(project, dict):
        service_name = project.get("name", project.get("slug", "unknown"))
    else:
        service_name = str(project) if project else "unknown"

    environment = payload.get("tags", {})
    if isinstance(environment, dict):
        env_tag = next(
            (v for k, v in environment.items() if k == "environment"), "production"
        )
        environment = str(env_tag)
    else:
        environment = "production"

    level = payload.get("level", "error")
    severity_map = {
        "fatal": IncidentSeverity.SEV1,
        "error": IncidentSeverity.SEV2,
        "warning": IncidentSeverity.SEV3,
        "info": IncidentSeverity.SEV4,
    }
    severity = severity_map.get(level, IncidentSeverity.SEV2)

    stacktrace = payload.get("stacktrace", {})
    stack_traces: list[str] = []
    if isinstance(stacktrace, dict):
        frames = stacktrace.get("frames", [])
        if frames:
            trace_parts = []
            for frame in frames:
                function = frame.get("function", "unknown")
                filename = frame.get("filename", frame.get("abs_path", ""))
                trace_parts.append(f"  at {function} ({filename})")
            stack_traces = ["\n".join(trace_parts)]

    return {
        "external_event_id": str(external_event_id),
        "title": str(title),
        "severity": severity,
        "service": str(service_name),
        "environment": str(environment),
        "description": str(payload.get("culprit", "")),
        "stack_traces": stack_traces,
    }


# ------------------------------------------------------------------
# Webhook endpoints
# ------------------------------------------------------------------


@router.post(
    "/pagerduty",
    response_model=WebhookResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def pagerduty_webhook(
    payload: dict[str, Any],
    svc: ServiceDep,
) -> dict:
    if not payload:
        raise HTTPException(status_code=400, detail="Empty payload")

    try:
        normalized = normalize_pagerduty(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid PagerDuty payload: {e}")

    try:
        incident = svc.ingest_webhook(
            source=IncidentSource.PAGERDUTY,
            external_event_id=normalized["external_event_id"],
            title=normalized["title"],
            severity=normalized["severity"],
            service=normalized["service"],
            environment=normalized["environment"],
            description=normalized["description"],
            stack_traces=normalized["stack_traces"],
            raw_payload=payload,
        )
        return {
            "incident_id": incident["id"],
            "status": incident["status"],
            "message": "Incident created from PagerDuty webhook",
        }
    except DuplicateWebhookError as e:
        return {
            "incident_id": e.existing_incident["id"],
            "status": e.existing_incident["status"],
            "message": "Duplicate webhook - returning existing incident",
        }


@router.post(
    "/sentry",
    response_model=WebhookResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def sentry_webhook(
    payload: dict[str, Any],
    svc: ServiceDep,
) -> dict:
    if not payload:
        raise HTTPException(status_code=400, detail="Empty payload")

    try:
        normalized = normalize_sentry(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Sentry payload: {e}")

    try:
        incident = svc.ingest_webhook(
            source=IncidentSource.SENTRY,
            external_event_id=normalized["external_event_id"],
            title=normalized["title"],
            severity=normalized["severity"],
            service=normalized["service"],
            environment=normalized["environment"],
            description=normalized["description"],
            stack_traces=normalized["stack_traces"],
            raw_payload=payload,
        )
        return {
            "incident_id": incident["id"],
            "status": incident["status"],
            "message": "Incident created from Sentry webhook",
        }
    except DuplicateWebhookError as e:
        return {
            "incident_id": e.existing_incident["id"],
            "status": e.existing_incident["status"],
            "message": "Duplicate webhook - returning existing incident",
        }
