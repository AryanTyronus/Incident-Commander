from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.db import get_connection, initialize_database
from backend.app.models.enums import IncidentSeverity, IncidentSource, IncidentStatus
from backend.app.repositories import IncidentRepository

INCIDENT_COLS = (
    "id, source, title, severity, service, environment, "
    "status, description, stack_traces, created_at, updated_at, raw_payload"
)
INCIDENT_PH = ", ".join(["?"] * 12)
INCIDENT_SQL = f"INSERT INTO incidents ({INCIDENT_COLS}) VALUES ({INCIDENT_PH})"

EVENT_COLS = (
    "id, incident_id, event_type, source, external_event_id, "
    "old_status, new_status, payload, created_at"
)
EVENT_PH = ", ".join(["?"] * 9)
EVENT_SQL = f"INSERT INTO incident_events ({EVENT_COLS}) VALUES ({EVENT_PH})"


class TestDatabaseInitialization:
    def test_tables_created(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = get_connection(db_path)
            initialize_database(conn)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t["name"] for t in tables}
            assert "incidents" in table_names
            assert "incident_events" in table_names
            conn.close()
        finally:
            os.unlink(db_path)

    def test_idempotent_initialization(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = get_connection(db_path)
            initialize_database(conn)
            initialize_database(conn)  # second call should not fail
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t["name"] for t in tables}
            assert "incidents" in table_names
            conn.close()
        finally:
            os.unlink(db_path)


class TestForeignKeyConstraint:
    def test_event_references_valid_incident(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = get_connection(db_path)
            initialize_database(conn)

            incident_id = str(uuid4())
            now_iso = datetime.now(UTC).isoformat()
            conn.execute(
                INCIDENT_SQL,
                (
                    incident_id, "MANUAL", "Test", "SEV1", "svc", "prod",
                    "RECEIVED", "", "[]", now_iso, now_iso, "{}",
                ),
            )
            conn.commit()

            # This should succeed
            event_id = str(uuid4())
            conn.execute(
                EVENT_SQL,
                (event_id, incident_id, "test", None, None, None, None, "{}", now_iso),
            )
            conn.commit()

            # This should fail - foreign key violation
            with pytest.raises(Exception):
                bad_event_id = str(uuid4())
                bad_incident_id = str(uuid4())
                conn.execute(
                    EVENT_SQL,
                    (
                        bad_event_id, bad_incident_id, "test",
                        None, None, None, None, "{}", now_iso,
                    ),
                )
                conn.commit()

            conn.close()
        finally:
            os.unlink(db_path)


class TestUniqueConstraint:
    def test_duplicate_event_constraint(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            repo = IncidentRepository(db_path)
            incident = repo.create_incident(
                id=uuid4(),
                source=IncidentSource.MANUAL.value,
                title="Constraint test",
                severity=IncidentSeverity.SEV1.value,
                service="svc",
                environment="prod",
                status=IncidentStatus.RECEIVED.value,
                description="",
                stack_traces=[],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                raw_payload={},
            )

            repo.record_event(
                id=uuid4(),
                incident_id=incident["id"],
                event_type="external_event",
                source="PAGERDUTY",
                external_event_id="dup-test",
                old_status=None,
                new_status=IncidentStatus.RECEIVED.value,
                payload={"external_event_id": "dup-test"},
                created_at=datetime.now(UTC),
            )

            # Same source + external_event_id should fail
            with pytest.raises(Exception):
                repo.record_event(
                    id=uuid4(),
                    incident_id=incident["id"],
                    event_type="external_event",
                    source="PAGERDUTY",
                    external_event_id="dup-test",
                    old_status=None,
                    new_status=IncidentStatus.RECEIVED.value,
                    payload={"external_event_id": "dup-test"},
                    created_at=datetime.now(UTC),
                )

            repo.close()
        finally:
            os.unlink(db_path)


class TestRepositoryRecreation:
    def test_data_survives_new_connection(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            repo1 = IncidentRepository(db_path)
            incident = repo1.create_incident(
                id=uuid4(),
                source=IncidentSource.SENTRY.value,
                title="Recreation test",
                severity=IncidentSeverity.SEV3.value,
                service="svc",
                environment="staging",
                status=IncidentStatus.RECEIVED.value,
                description="test desc",
                stack_traces=["trace1"],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                raw_payload={"key": "val"},
            )
            repo1.close()

            repo2 = IncidentRepository(db_path)
            fetched = repo2.get_incident(incident["id"])
            assert fetched is not None
            assert fetched["title"] == "Recreation test"
            assert fetched["stack_traces"] == ["trace1"]
            assert fetched["raw_payload"] == {"key": "val"}
            repo2.close()
        finally:
            os.unlink(db_path)
