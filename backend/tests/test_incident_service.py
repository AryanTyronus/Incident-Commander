from __future__ import annotations

import os
import tempfile
from uuid import UUID, uuid4

import pytest

from backend.app.models.enums import IncidentSeverity, IncidentSource, IncidentStatus
from backend.app.repositories import IncidentRepository
from backend.app.services.incident_service import (
    DuplicateWebhookError,
    IncidentNotFoundError,
    IncidentService,
    InvalidTransitionError,
)


@pytest.fixture()
def repo() -> IncidentRepository:
    """Provide a repository backed by a temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    repository = IncidentRepository(db_path)
    yield repository
    repository.close()
    os.unlink(db_path)


@pytest.fixture()
def svc(repo: IncidentRepository) -> IncidentService:
    return IncidentService(repo)


class TestIncidentCreation:
    def test_create_incident_generates_uuid(self, svc: IncidentService) -> None:
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        assert isinstance(incident["id"], UUID)

    def test_create_incident_utc_timestamps(self, svc: IncidentService) -> None:
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        assert incident["created_at"].tzinfo is not None
        assert incident["updated_at"].tzinfo is not None
        assert incident["created_at"] <= incident["updated_at"]

    def test_create_incident_initial_status(self, svc: IncidentService) -> None:
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        assert incident["status"] == IncidentStatus.RECEIVED.value

    def test_create_incident_raw_payload_preserved(self, svc: IncidentService) -> None:
        raw = {"key": "value", "nested": {"a": [1, 2, 3]}}
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
            raw_payload=raw,
        )
        assert incident["raw_payload"] == raw

    def test_create_incident_stack_traces(self, svc: IncidentService) -> None:
        traces = ["at foo (bar.py:10)", "at baz (qux.py:20)"]
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
            stack_traces=traces,
        )
        assert incident["stack_traces"] == traces


class TestIncidentRetrieval:
    def test_get_incident(self, svc: IncidentService) -> None:
        created = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        fetched = svc.get_incident(created["id"])
        assert fetched["id"] == created["id"]

    def test_get_incident_not_found(self, svc: IncidentService) -> None:
        with pytest.raises(IncidentNotFoundError):
            svc.get_incident(uuid4())

    def test_list_incidents(self, svc: IncidentService) -> None:
        for i in range(3):
            svc.create_incident(
                source=IncidentSource.MANUAL,
                title=f"Incident {i}",
                severity=IncidentSeverity.SEV2,
                service="svc",
                environment="prod",
            )
        incidents, total = svc.list_incidents()
        assert len(incidents) == 3
        assert total == 3

    def test_list_incidents_pagination(self, svc: IncidentService) -> None:
        for i in range(5):
            svc.create_incident(
                source=IncidentSource.MANUAL,
                title=f"Incident {i}",
                severity=IncidentSeverity.SEV2,
                service="svc",
                environment="prod",
            )
        incidents, total = svc.list_incidents(limit=2, offset=0)
        assert len(incidents) == 2
        assert total == 5


class TestStateMachine:
    def test_valid_transition_received_to_triaging(self, svc: IncidentService) -> None:
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        updated = svc.transition_status(incident["id"], IncidentStatus.TRIAGING)
        assert updated["status"] == IncidentStatus.TRIAGING.value

    def test_valid_full_lifecycle(self, svc: IncidentService) -> None:
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        transitions = [
            IncidentStatus.TRIAGING,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.SYNTHESIZING,
            IncidentStatus.AWAITING_APPROVAL,
            IncidentStatus.RESOLVED,
        ]
        current = incident
        for target in transitions:
            current = svc.transition_status(current["id"], target)
            assert current["status"] == target.value

    def test_valid_triaging_to_failed(self, svc: IncidentService) -> None:
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        updated = svc.transition_status(incident["id"], IncidentStatus.TRIAGING)
        updated = svc.transition_status(updated["id"], IncidentStatus.FAILED)
        assert updated["status"] == IncidentStatus.FAILED.value

    def test_invalid_received_to_resolved(self, svc: IncidentService) -> None:
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        with pytest.raises(InvalidTransitionError):
            svc.transition_status(incident["id"], IncidentStatus.RESOLVED)

    def test_invalid_received_to_awaiting_approval(self, svc: IncidentService) -> None:
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        with pytest.raises(InvalidTransitionError):
            svc.transition_status(incident["id"], IncidentStatus.AWAITING_APPROVAL)

    def test_invalid_resolved_to_investigating(self, svc: IncidentService) -> None:
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        incident = svc.transition_status(incident["id"], IncidentStatus.TRIAGING)
        incident = svc.transition_status(incident["id"], IncidentStatus.INVESTIGATING)
        incident = svc.transition_status(incident["id"], IncidentStatus.SYNTHESIZING)
        incident = svc.transition_status(incident["id"], IncidentStatus.AWAITING_APPROVAL)
        incident = svc.transition_status(incident["id"], IncidentStatus.RESOLVED)
        with pytest.raises(InvalidTransitionError):
            svc.transition_status(incident["id"], IncidentStatus.INVESTIGATING)

    def test_invalid_failed_to_resolved(self, svc: IncidentService) -> None:
        incident = svc.create_incident(
            source=IncidentSource.MANUAL,
            title="Test",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        incident = svc.transition_status(incident["id"], IncidentStatus.TRIAGING)
        incident = svc.transition_status(incident["id"], IncidentStatus.FAILED)
        with pytest.raises(InvalidTransitionError):
            svc.transition_status(incident["id"], IncidentStatus.RESOLVED)


class TestWebhookIngestion:
    def test_ingest_webhook_creates_incident(self, svc: IncidentService) -> None:
        incident = svc.ingest_webhook(
            source=IncidentSource.PAGERDUTY,
            external_event_id="pd-evt-001",
            title="Alert",
            severity=IncidentSeverity.SEV1,
            service="svc",
            environment="prod",
        )
        assert incident["source"] == IncidentSource.PAGERDUTY.value
        assert incident["status"] == IncidentStatus.RECEIVED.value

    def test_ingest_webhook_deduplication(self, svc: IncidentService) -> None:
        incident1 = svc.ingest_webhook(
            source=IncidentSource.SENTRY,
            external_event_id="sentry-evt-001",
            title="Error",
            severity=IncidentSeverity.SEV2,
            service="svc",
            environment="prod",
        )
        with pytest.raises(DuplicateWebhookError) as exc_info:
            svc.ingest_webhook(
                source=IncidentSource.SENTRY,
                external_event_id="sentry-evt-001",
                title="Error",
                severity=IncidentSeverity.SEV2,
                service="svc",
                environment="prod",
            )
        assert exc_info.value.existing_incident["id"] == incident1["id"]


class TestPersistence:
    def test_data_survives_repository_recreation(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            repo1 = IncidentRepository(db_path)
            incident = repo1.create_incident(
                id=uuid4(),
                source=IncidentSource.MANUAL.value,
                title="Persist test",
                severity=IncidentSeverity.SEV1.value,
                service="svc",
                environment="prod",
                status=IncidentStatus.RECEIVED.value,
                description="",
                stack_traces=[],
                created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                updated_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                raw_payload={"persist": True},
            )
            repo1.close()

            repo2 = IncidentRepository(db_path)
            fetched = repo2.get_incident(incident["id"])
            assert fetched is not None
            assert fetched["title"] == "Persist test"
            assert fetched["raw_payload"] == {"persist": True}
            repo2.close()
        finally:
            os.unlink(db_path)
