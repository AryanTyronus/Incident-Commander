from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.app.llm.fake import FakeLLMProvider
from backend.app.models.agent_schemas import AgentRun, AgentRunStatus
from backend.app.repositories import AgentRunRepository, IncidentRepository


def _create_test_incident(repo: IncidentRepository, incident_id: UUID) -> dict[str, Any]:
    """Create a test incident for foreign key compliance."""
    return repo.create_incident(
        id=incident_id,
        source="MANUAL",
        title="Test Incident",
        severity="SEV1",
        service="test-service",
        environment="production",
        status="RECEIVED",
        description="Test",
        stack_traces=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        raw_payload={},
    )


class TestAgentRunRepository:
    """Tests for AgentRunRepository SQLite persistence."""

    def test_create_and_get_run(self, tmp_db: str) -> None:
        incident_repo = IncidentRepository(tmp_db)
        run_repo = AgentRunRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        run = AgentRun(
            id=uuid4(),
            incident_id=incident_id,
            agent_name="test_agent",
            status=AgentRunStatus.PENDING,
        )

        created = run_repo.create_run(run)
        fetched = run_repo.get_run(created.id)

        assert fetched is not None
        assert fetched.agent_name == "test_agent"
        assert fetched.status == AgentRunStatus.PENDING
        run_repo.close()
        incident_repo.close()

    def test_update_run(self, tmp_db: str) -> None:
        incident_repo = IncidentRepository(tmp_db)
        run_repo = AgentRunRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        run = AgentRun(
            id=uuid4(),
            incident_id=incident_id,
            agent_name="test_agent",
            status=AgentRunStatus.PENDING,
        )

        created = run_repo.create_run(run)
        created.status = AgentRunStatus.COMPLETED
        created.completed_at = datetime.now(UTC)

        updated = run_repo.update_run(created)
        assert updated.status == AgentRunStatus.COMPLETED
        assert updated.completed_at is not None
        run_repo.close()
        incident_repo.close()

    def test_get_runs_for_incident(self, tmp_db: str) -> None:
        incident_repo = IncidentRepository(tmp_db)
        run_repo = AgentRunRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        for i in range(3):
            run = AgentRun(
                id=uuid4(),
                incident_id=incident_id,
                agent_name=f"agent_{i}",
                status=AgentRunStatus.PENDING,
            )
            run_repo.create_run(run)

        runs = run_repo.get_runs_for_incident(incident_id)
        assert len(runs) == 3

        other_runs = run_repo.get_runs_for_incident(uuid4())
        assert len(other_runs) == 0
        run_repo.close()
        incident_repo.close()

    def test_run_with_output(self, tmp_db: str) -> None:
        incident_repo = IncidentRepository(tmp_db)
        run_repo = AgentRunRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        run = AgentRun(
            id=uuid4(),
            incident_id=incident_id,
            agent_name="test_agent",
            status=AgentRunStatus.COMPLETED,
            output={"summary": "done", "findings": []},
            completed_at=datetime.now(UTC),
        )

        created = run_repo.create_run(run)
        fetched = run_repo.get_run(created.id)

        assert fetched is not None
        assert fetched.output == {"summary": "done", "findings": []}
        run_repo.close()
        incident_repo.close()

    def test_run_with_error(self, tmp_db: str) -> None:
        incident_repo = IncidentRepository(tmp_db)
        run_repo = AgentRunRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        run = AgentRun(
            id=uuid4(),
            incident_id=incident_id,
            agent_name="test_agent",
            status=AgentRunStatus.FAILED,
            error="RuntimeError: something broke",
            completed_at=datetime.now(UTC),
        )

        created = run_repo.create_run(run)
        fetched = run_repo.get_run(created.id)

        assert fetched is not None
        assert fetched.error == "RuntimeError: something broke"
        run_repo.close()
        incident_repo.close()

    def test_get_nonexistent_run(self, tmp_db: str) -> None:
        run_repo = AgentRunRepository(tmp_db)
        assert run_repo.get_run(uuid4()) is None
        run_repo.close()


class TestAgentService:
    """Tests for AgentService."""

    def test_get_agent_runs(self, tmp_db: str) -> None:
        from backend.app.services.agent_service import AgentService

        incident_repo = IncidentRepository(tmp_db)
        run_repo = AgentRunRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        llm = FakeLLMProvider(responses=[])
        service = AgentService(
            llm=llm,
            agent_run_repo=run_repo,
            incident_repo=incident_repo,
        )

        for i in range(2):
            run = AgentRun(
                id=uuid4(),
                incident_id=incident_id,
                agent_name=f"agent_{i}",
                status=AgentRunStatus.COMPLETED,
            )
            run_repo.create_run(run)

        runs = service.get_agent_runs(incident_id)
        assert len(runs) == 2
        run_repo.close()
        incident_repo.close()
