from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.app.models.enums import IncidentSeverity, IncidentSource, IncidentStatus
from backend.app.repositories import IncidentRepository

# Valid state transitions
VALID_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.RECEIVED: {IncidentStatus.TRIAGING},
    IncidentStatus.TRIAGING: {IncidentStatus.INVESTIGATING, IncidentStatus.FAILED},
    IncidentStatus.INVESTIGATING: {IncidentStatus.SYNTHESIZING, IncidentStatus.FAILED},
    IncidentStatus.SYNTHESIZING: {IncidentStatus.AWAITING_APPROVAL, IncidentStatus.FAILED},
    IncidentStatus.AWAITING_APPROVAL: {IncidentStatus.RESOLVED, IncidentStatus.FAILED},
    IncidentStatus.RESOLVED: set(),
    IncidentStatus.FAILED: set(),
}


class InvalidTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""

    def __init__(self, current: IncidentStatus, target: IncidentStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid transition: {current.value} -> {target.value}"
        )


class IncidentNotFoundError(Exception):
    """Raised when an incident is not found."""

    def __init__(self, incident_id: UUID) -> None:
        self.incident_id = incident_id
        super().__init__(f"Incident not found: {incident_id}")


class DuplicateWebhookError(Exception):
    """Raised when a duplicate webhook is received."""

    def __init__(self, existing_incident: dict[str, Any]) -> None:
        self.existing_incident = existing_incident
        super().__init__("Duplicate webhook event")


class IncidentService:
    """Business logic for incident management."""

    def __init__(self, repo: IncidentRepository) -> None:
        self._repo = repo

    def create_incident(
        self,
        *,
        source: IncidentSource,
        title: str,
        severity: IncidentSeverity,
        service: str,
        environment: str,
        description: str = "",
        stack_traces: list[str] | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        incident_id = uuid4()
        return self._repo.create_incident(
            id=incident_id,
            source=source.value,
            title=title,
            severity=severity.value,
            service=service,
            environment=environment,
            status=IncidentStatus.RECEIVED.value,
            description=description,
            stack_traces=stack_traces or [],
            created_at=now,
            updated_at=now,
            raw_payload=raw_payload or {},
        )

    def get_incident(self, incident_id: UUID) -> dict[str, Any]:
        incident = self._repo.get_incident(incident_id)
        if incident is None:
            raise IncidentNotFoundError(incident_id)
        return incident

    def list_incidents(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        incidents = self._repo.list_incidents(limit=limit, offset=offset)
        total = self._repo.count_incidents()
        return incidents, total

    def transition_status(
        self, incident_id: UUID, new_status: IncidentStatus
    ) -> dict[str, Any]:
        incident = self.get_incident(incident_id)
        current_status = IncidentStatus(incident["status"])

        if new_status not in VALID_TRANSITIONS.get(current_status, set()):
            raise InvalidTransitionError(current_status, new_status)

        updated = self._repo.update_incident_status(incident_id, new_status.value)

        self._repo.record_event(
            id=uuid4(),
            incident_id=incident_id,
            event_type="status_change",
            old_status=current_status.value,
            new_status=new_status.value,
            payload={"reason": "manual_transition"},
            created_at=datetime.now(UTC),
        )

        return updated

    def ingest_webhook(
        self,
        *,
        source: IncidentSource,
        external_event_id: str,
        title: str,
        severity: IncidentSeverity,
        service: str,
        environment: str,
        description: str = "",
        stack_traces: list[str] | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ingest a webhook, enforcing deduplication."""
        existing = self._repo.find_incident_by_external_event(
            source=source.value, external_event_id=external_event_id
        )
        if existing is not None:
            raise DuplicateWebhookError(existing)

        incident = self.create_incident(
            source=source,
            title=title,
            severity=severity,
            service=service,
            environment=environment,
            description=description,
            stack_traces=stack_traces,
            raw_payload=raw_payload,
        )

        self._repo.record_event(
            id=uuid4(),
            incident_id=incident["id"],
            event_type="external_event",
            source=source.value,
            external_event_id=external_event_id,
            old_status=None,
            new_status=IncidentStatus.RECEIVED.value,
            payload={
                "source": source.value,
                "external_event_id": external_event_id,
            },
            created_at=datetime.now(UTC),
        )

        return incident
