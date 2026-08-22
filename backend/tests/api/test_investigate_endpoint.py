"""Tests for the non-blocking investigation endpoint and its background runner.

``POST /api/incidents/{id}/investigate`` used to await the whole investigation -
minutes of LLM and agent work - before answering. It now validates, schedules,
and returns 202.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient

from backend.app.api.incidents import start_investigation
from backend.app.dependencies import get_investigation_runner
from backend.app.events.model import EventType, IncidentEvent
from backend.app.events.publisher import event_publisher
from backend.app.main import app
from backend.app.models.agent_schemas import InvestigationStage, InvestigationState
from backend.app.repositories import IncidentRepository, InvestigationRepository
from backend.app.services.incident_service import IncidentService
from backend.app.services.investigation_runner import InvestigationRunner


class RecordingRunner:
    """Stand-in for InvestigationRunner that records what it was asked to run."""

    def __init__(self) -> None:
        self.incident_ids: list[UUID] = []

    async def run(self, incident_id: UUID) -> None:
        self.incident_ids.append(incident_id)


class NeverFinishingRunner:
    """Runner whose work never completes, to prove the endpoint does not await."""

    def __init__(self) -> None:
        self.started = False

    async def run(self, incident_id: UUID) -> None:
        self.started = True
        await asyncio.Event().wait()


def _create_incident(client: TestClient) -> str:
    resp = client.post(
        "/api/incidents",
        json={
            "source": "MANUAL",
            "title": "Investigate endpoint test",
            "severity": "SEV2",
            "service": "payment-service",
            "environment": "production",
            "description": "Background investigation test",
            "stack_traces": [],
            "raw_payload": {},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture()
def recording_runner() -> Any:
    runner = RecordingRunner()
    app.dependency_overrides[get_investigation_runner] = lambda: runner
    yield runner
    app.dependency_overrides.pop(get_investigation_runner, None)


class TestInvestigateEndpointAccepts:
    """The HTTP contract: validate, schedule, answer 202."""

    def test_returns_202_accepted(self, client: TestClient, recording_runner: Any) -> None:
        incident_id = _create_incident(client)

        resp = client.post(f"/api/incidents/{incident_id}/investigate")

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["incident_id"] == incident_id
        assert body["investigation_status"] == InvestigationStage.PLANNING.value
        assert "background" in body["message"].lower()

    def test_schedules_the_background_investigation(
        self, client: TestClient, recording_runner: Any
    ) -> None:
        incident_id = _create_incident(client)

        client.post(f"/api/incidents/{incident_id}/investigate")

        # TestClient drains background tasks before returning.
        assert recording_runner.incident_ids == [UUID(incident_id)]

    def test_unknown_incident_returns_404_and_schedules_nothing(
        self, client: TestClient, recording_runner: Any
    ) -> None:
        resp = client.post(f"/api/incidents/{uuid4()}/investigate")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Incident not found"
        assert recording_runner.incident_ids == []

    def test_running_investigation_returns_409_and_schedules_nothing(
        self, client: TestClient, tmp_db: str, recording_runner: Any
    ) -> None:
        incident_id = _create_incident(client)
        _persist_stage(tmp_db, UUID(incident_id), InvestigationStage.EXECUTING)

        resp = client.post(f"/api/incidents/{incident_id}/investigate")

        assert resp.status_code == 409
        assert "already running" in resp.json()["detail"]
        assert recording_runner.incident_ids == []

    def test_finished_investigation_can_be_restarted(
        self, client: TestClient, tmp_db: str, recording_runner: Any
    ) -> None:
        incident_id = _create_incident(client)
        _persist_stage(tmp_db, UUID(incident_id), InvestigationStage.COMPLETED)

        resp = client.post(f"/api/incidents/{incident_id}/investigate")

        assert resp.status_code == 202
        assert recording_runner.incident_ids == [UUID(incident_id)]


class TestInvestigateEndpointDoesNotWait:
    """The endpoint must hand work to the background, not await it."""

    async def test_endpoint_returns_before_the_investigation_starts(
        self, tmp_db: str
    ) -> None:
        incident_id = _seed_incident(tmp_db)
        runner = NeverFinishingRunner()
        repo = IncidentRepository(tmp_db)
        investigation_repo = InvestigationRepository(tmp_db)
        background_tasks = BackgroundTasks()

        try:
            # Would hang forever if the endpoint awaited the investigation.
            response = await asyncio.wait_for(
                start_investigation(
                    incident_id=incident_id,
                    background_tasks=background_tasks,
                    svc=IncidentService(repo),
                    investigation_repo=investigation_repo,
                    runner=runner,
                ),
                timeout=5,
            )
        finally:
            repo.close()
            investigation_repo.close()

        assert response["investigation_status"] == InvestigationStage.PLANNING.value
        assert runner.started is False, "investigation must not run inside the request"

        # The work is queued as a managed Starlette background task instead.
        assert len(background_tasks.tasks) == 1
        task = background_tasks.tasks[0]
        assert task.func == runner.run
        assert task.args == (incident_id,)


class TestBackgroundRunner:
    """The runner owns failure handling for work that outlives the request."""

    async def test_runs_the_commander_with_its_own_repository(self, tmp_db: str) -> None:
        incident_id = _seed_incident(tmp_db)
        seen: dict[str, Any] = {}

        class SucceedingCommander:
            def __init__(self, repo: IncidentRepository) -> None:
                self._repo = repo

            async def investigate(self, target: UUID) -> None:
                # The runner must supply a live connection, not the request's.
                seen["incident"] = self._repo.get_incident(target)
                seen["investigated"] = target

        runner = InvestigationRunner(
            db_path=tmp_db, commander_factory=SucceedingCommander
        )
        await runner.run(incident_id)

        assert seen["investigated"] == incident_id
        assert seen["incident"] is not None

    async def test_failure_is_persisted_and_published(self, tmp_db: str) -> None:
        incident_id = _seed_incident(tmp_db)

        class FailingCommander:
            def __init__(self, repo: IncidentRepository) -> None:
                self._repo = repo

            async def investigate(self, target: UUID) -> None:
                raise RuntimeError("ollama unreachable")

        with _capture_events(incident_id) as published:
            runner = InvestigationRunner(
                db_path=tmp_db, commander_factory=FailingCommander
            )
            await runner.run(incident_id)  # must not raise

        state = _load_state(tmp_db, incident_id)
        assert state is not None
        assert state.status == InvestigationStage.FAILED
        assert any("ollama unreachable" in err for err in state.errors)

        assert EventType.INVESTIGATION_FAILED in [e.event_type for e in published]
        assert EventType.INVESTIGATION_FAILED.value in _audit_event_types(tmp_db, incident_id)

    async def test_failure_is_not_silently_swallowed(
        self, tmp_db: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        incident_id = _seed_incident(tmp_db)

        class FailingCommander:
            def __init__(self, repo: IncidentRepository) -> None:
                pass

            async def investigate(self, target: UUID) -> None:
                raise RuntimeError("boom")

        runner = InvestigationRunner(db_path=tmp_db, commander_factory=FailingCommander)
        with caplog.at_level("ERROR"):
            await runner.run(incident_id)

        assert "boom" in caplog.text

    async def test_already_running_does_not_overwrite_state(self, tmp_db: str) -> None:
        from backend.app.agents.commander import InvestigationAlreadyRunningError

        incident_id = _seed_incident(tmp_db)
        _persist_stage(tmp_db, incident_id, InvestigationStage.EXECUTING)

        class BusyCommander:
            def __init__(self, repo: IncidentRepository) -> None:
                pass

            async def investigate(self, target: UUID) -> None:
                raise InvestigationAlreadyRunningError(str(target))

        runner = InvestigationRunner(db_path=tmp_db, commander_factory=BusyCommander)
        await runner.run(incident_id)

        state = _load_state(tmp_db, incident_id)
        assert state is not None
        assert state.status == InvestigationStage.EXECUTING

    async def test_missing_incident_does_not_raise(self, tmp_db: str) -> None:
        """The runner is a background task: it has no caller left to catch."""
        IncidentRepository(tmp_db).close()  # ensure the schema exists

        runner = InvestigationRunner(
            db_path=tmp_db, commander_factory=_commander_raising_not_found
        )
        await runner.run(uuid4())

    def test_dependency_provides_a_runner_bound_to_the_configured_db(
        self, tmp_db: str
    ) -> None:
        runner = get_investigation_runner()

        assert isinstance(runner, InvestigationRunner)
        assert runner._db_path == tmp_db


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _commander_raising_not_found(repo: IncidentRepository) -> Any:
    from backend.app.services.incident_service import IncidentNotFoundError

    class Commander:
        async def investigate(self, target: UUID) -> None:
            raise IncidentNotFoundError(target)

    return Commander()


def _seed_incident(db_path: str) -> UUID:
    """Insert an incident directly, satisfying foreign-key constraints."""
    incident_id = uuid4()
    repo = IncidentRepository(db_path)
    try:
        repo.create_incident(
            id=incident_id,
            source="MANUAL",
            title="Background runner test",
            severity="SEV1",
            service="payment-service",
            environment="production",
            status="RECEIVED",
            description="Seeded incident",
            stack_traces=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            raw_payload={},
        )
    finally:
        repo.close()
    return incident_id


def _persist_stage(db_path: str, incident_id: UUID, stage: InvestigationStage) -> None:
    state = InvestigationState(
        incident_id=incident_id, status=stage, current_stage=stage
    )
    now = datetime.now(UTC)
    repo = InvestigationRepository(db_path)
    try:
        existing = repo.get_by_incident_id(incident_id)
        if existing is None:
            repo.create_investigation(
                id=uuid4(),
                incident_id=incident_id,
                stage=stage.value,
                state_json=state.model_dump_json(),
                created_at=now,
                updated_at=now,
            )
        else:
            repo.update_investigation(
                investigation_id=existing["id"],
                stage=stage.value,
                state_json=state.model_dump_json(),
                updated_at=now,
            )
    finally:
        repo.close()


def _load_state(db_path: str, incident_id: UUID) -> InvestigationState | None:
    repo = InvestigationRepository(db_path)
    try:
        record = repo.get_by_incident_id(incident_id)
    finally:
        repo.close()
    if record is None:
        return None
    return InvestigationState.model_validate_json(record["state_json"])


def _audit_event_types(db_path: str, incident_id: UUID) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT event_type FROM incident_events WHERE incident_id = ?",
            (str(incident_id),),
        ).fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]


class _capture_events:
    """Collect everything published for one incident."""

    def __init__(self, incident_id: UUID) -> None:
        self._incident_id = incident_id
        self.events: list[IncidentEvent] = []

    def __enter__(self) -> list[IncidentEvent]:
        event_publisher.subscribe(self._incident_id, self.events.append)
        return self.events

    def __exit__(self, *exc: object) -> None:
        event_publisher.unsubscribe(self._incident_id, self.events.append)
