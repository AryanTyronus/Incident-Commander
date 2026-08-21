from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from backend.app.models.agent_schemas import (
    AgentResult,
    AgentRun,
    AgentRunStatus,
    InvestigationStage,
    InvestigationState,
)
from backend.app.repositories import (
    IncidentRepository,
    InvestigationRepository,
)


def _create_test_incident(
    repo: IncidentRepository, incident_id: UUID
) -> dict:
    """Create a test incident for foreign key compliance."""
    return repo.create_incident(
        id=incident_id,
        source="MANUAL",
        title="Test Incident",
        severity="SEV1",
        service="test-service",
        environment="production",
        status="RECEIVED",
        description="Test incident for persistence",
        stack_traces=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        raw_payload={},
    )


class TestInvestigationRepository:
    """Tests for InvestigationRepository SQLite persistence."""

    def test_create_and_get_investigation(self, tmp_db: str) -> None:
        incident_repo = IncidentRepository(tmp_db)
        inv_repo = InvestigationRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        inv_id = uuid4()
        now = datetime.now(UTC)
        state = InvestigationState(
            incident_id=incident_id,
            status=InvestigationStage.PLANNING,
            current_stage=InvestigationStage.PLANNING,
        )

        created = inv_repo.create_investigation(
            id=inv_id,
            incident_id=incident_id,
            stage=state.status.value,
            state_json=state.model_dump_json(),
            created_at=now,
            updated_at=now,
        )

        assert created is not None
        assert created["id"] == inv_id
        assert created["incident_id"] == incident_id
        assert created["stage"] == "PLANNING"

        fetched = inv_repo.get_investigation(inv_id)
        assert fetched is not None
        assert fetched["id"] == inv_id

        inv_repo.close()
        incident_repo.close()

    def test_get_by_incident_id(self, tmp_db: str) -> None:
        incident_repo = IncidentRepository(tmp_db)
        inv_repo = InvestigationRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        inv_id = uuid4()
        now = datetime.now(UTC)
        state = InvestigationState(
            incident_id=incident_id,
            status=InvestigationStage.EXECUTING,
            current_stage=InvestigationStage.EXECUTING,
        )

        inv_repo.create_investigation(
            id=inv_id,
            incident_id=incident_id,
            stage=state.status.value,
            state_json=state.model_dump_json(),
            created_at=now,
            updated_at=now,
        )

        found = inv_repo.get_by_incident_id(incident_id)
        assert found is not None
        assert found["id"] == inv_id
        assert found["incident_id"] == incident_id

        inv_repo.close()
        incident_repo.close()

    def test_update_investigation(self, tmp_db: str) -> None:
        incident_repo = IncidentRepository(tmp_db)
        inv_repo = InvestigationRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        inv_id = uuid4()
        now = datetime.now(UTC)
        state = InvestigationState(
            incident_id=incident_id,
            status=InvestigationStage.PLANNING,
            current_stage=InvestigationStage.PLANNING,
        )

        inv_repo.create_investigation(
            id=inv_id,
            incident_id=incident_id,
            stage=state.status.value,
            state_json=state.model_dump_json(),
            created_at=now,
            updated_at=now,
        )

        state.status = InvestigationStage.EXECUTING
        state.current_stage = InvestigationStage.EXECUTING
        updated = inv_repo.update_investigation(
            investigation_id=inv_id,
            stage=state.status.value,
            state_json=state.model_dump_json(),
            updated_at=datetime.now(UTC),
        )

        assert updated["stage"] == "EXECUTING"

        inv_repo.close()
        incident_repo.close()

    def test_json_round_trip(self, tmp_db: str) -> None:
        incident_repo = IncidentRepository(tmp_db)
        inv_repo = InvestigationRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        run = AgentRun(
            id=uuid4(),
            incident_id=incident_id,
            agent_name="test_agent",
            status=AgentRunStatus.COMPLETED,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            input={"key": "value"},
            output={"summary": "done", "findings": [{"type": "test"}]},
            metadata={"version": 1},
        )

        finding = AgentResult(
            agent_name="test_agent",
            summary="done",
            findings=[{"type": "test"}],
            confidence=0.9,
        )
        state = InvestigationState(
            incident_id=incident_id,
            status=InvestigationStage.COMPLETED,
            current_stage=InvestigationStage.COMPLETED,
            completed_runs=[run],
            findings=[finding],
            errors=["test error"],
        )

        inv_id = uuid4()
        now = datetime.now(UTC)
        inv_repo.create_investigation(
            id=inv_id,
            incident_id=incident_id,
            stage=state.status.value,
            state_json=state.model_dump_json(),
            created_at=now,
            updated_at=now,
        )

        record = inv_repo.get_investigation(inv_id)
        loaded_state = InvestigationState.model_validate_json(record["state_json"])

        assert loaded_state.incident_id == state.incident_id
        assert loaded_state.status == state.status
        assert loaded_state.current_stage == state.current_stage
        assert len(loaded_state.completed_runs) == 1
        assert loaded_state.completed_runs[0].agent_name == "test_agent"
        assert loaded_state.completed_runs[0].output == run.output
        assert loaded_state.errors == ["test error"]
        assert len(loaded_state.findings) == 1
        assert loaded_state.findings[0].agent_name == "test_agent"
        assert loaded_state.findings[0].summary == "done"

        inv_repo.close()
        incident_repo.close()

    def test_foreign_key_constraint(self, tmp_db: str) -> None:
        inv_repo = InvestigationRepository(tmp_db)
        now = datetime.now(UTC)
        state = InvestigationState(
            incident_id=uuid4(),
            status=InvestigationStage.PLANNING,
            current_stage=InvestigationStage.PLANNING,
        )

        with pytest.raises(Exception):
            inv_repo.create_investigation(
                id=uuid4(),
                incident_id=uuid4(),
                stage=state.status.value,
                state_json=state.model_dump_json(),
                created_at=now,
                updated_at=now,
            )

        inv_repo.close()

    def test_unique_incident_constraint(self, tmp_db: str) -> None:
        incident_repo = IncidentRepository(tmp_db)
        inv_repo = InvestigationRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        now = datetime.now(UTC)
        state = InvestigationState(
            incident_id=incident_id,
            status=InvestigationStage.PLANNING,
            current_stage=InvestigationStage.PLANNING,
        )

        inv_repo.create_investigation(
            id=uuid4(),
            incident_id=incident_id,
            stage=state.status.value,
            state_json=state.model_dump_json(),
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(Exception):
            inv_repo.create_investigation(
                id=uuid4(),
                incident_id=incident_id,
                stage=state.status.value,
                state_json=state.model_dump_json(),
                created_at=now,
                updated_at=now,
            )

        inv_repo.close()
        incident_repo.close()

    def test_repository_recreation(self, tmp_db: str) -> None:
        """Most important test: state survives repository recreation."""
        incident_repo = IncidentRepository(tmp_db)
        inv_repo = InvestigationRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        inv_id = uuid4()
        now = datetime.now(UTC)
        state = InvestigationState(
            incident_id=incident_id,
            status=InvestigationStage.EXECUTING,
            current_stage=InvestigationStage.EXECUTING,
            errors=["some error occurred"],
        )

        inv_repo.create_investigation(
            id=inv_id,
            incident_id=incident_id,
            stage=state.status.value,
            state_json=state.model_dump_json(),
            created_at=now,
            updated_at=now,
        )

        inv_repo.close()
        incident_repo.close()

        inv_repo2 = InvestigationRepository(tmp_db)
        record = inv_repo2.get_investigation(inv_id)
        assert record is not None

        loaded_state = InvestigationState.model_validate_json(record["state_json"])
        assert loaded_state.incident_id == incident_id
        assert loaded_state.status == InvestigationStage.EXECUTING
        assert loaded_state.errors == ["some error occurred"]

        inv_repo2.close()

    def test_all_stages_persist(self, tmp_db: str) -> None:
        """Verify all investigation stages persist correctly."""
        incident_repo = IncidentRepository(tmp_db)
        inv_repo = InvestigationRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        stages = [
            InvestigationStage.PLANNING,
            InvestigationStage.EXECUTING,
            InvestigationStage.AGGREGATING,
            InvestigationStage.COMPLETED,
        ]

        inv_id = uuid4()

        for stage in stages:
            state = InvestigationState(
                incident_id=incident_id,
                status=stage,
                current_stage=stage,
            )
            if inv_repo.get_investigation(inv_id) is None:
                inv_repo.create_investigation(
                    id=inv_id,
                    incident_id=incident_id,
                    stage=stage.value,
                    state_json=state.model_dump_json(),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            else:
                inv_repo.update_investigation(
                    investigation_id=inv_id,
                    stage=stage.value,
                    state_json=state.model_dump_json(),
                    updated_at=datetime.now(UTC),
                )

        record = inv_repo.get_investigation(inv_id)
        assert record["stage"] == "COMPLETED"

        inv_repo.close()
        incident_repo.close()

    def test_failed_investigation_persists(self, tmp_db: str) -> None:
        """Verify failed investigations persist with errors."""
        incident_repo = IncidentRepository(tmp_db)
        inv_repo = InvestigationRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        state = InvestigationState(
            incident_id=incident_id,
            status=InvestigationStage.FAILED,
            current_stage=InvestigationStage.FAILED,
            errors=["PlanningError: LLM unavailable", "Agent failed: timeout"],
        )

        inv_id = uuid4()
        now = datetime.now(UTC)
        inv_repo.create_investigation(
            id=inv_id,
            incident_id=incident_id,
            stage=state.status.value,
            state_json=state.model_dump_json(),
            created_at=now,
            updated_at=now,
        )

        inv_repo.close()

        inv_repo2 = InvestigationRepository(tmp_db)
        record = inv_repo2.get_investigation(inv_id)
        loaded = InvestigationState.model_validate_json(record["state_json"])

        assert loaded.status == InvestigationStage.FAILED
        assert len(loaded.errors) == 2
        assert "PlanningError" in loaded.errors[0]
        assert "timeout" in loaded.errors[1]

        inv_repo2.close()
        incident_repo.close()

    def test_agent_references_survive_reload(self, tmp_db: str) -> None:
        """Verify agent run references survive reload."""
        incident_repo = IncidentRepository(tmp_db)
        inv_repo = InvestigationRepository(tmp_db)
        incident_id = uuid4()
        _create_test_incident(incident_repo, incident_id)

        run_id = uuid4()
        run = AgentRun(
            id=run_id,
            incident_id=incident_id,
            agent_name="log_triage",
            status=AgentRunStatus.COMPLETED,
            output={"summary": "Found errors"},
        )

        state = InvestigationState(
            incident_id=incident_id,
            status=InvestigationStage.COMPLETED,
            current_stage=InvestigationStage.COMPLETED,
            completed_runs=[run],
        )

        inv_id = uuid4()
        inv_repo.create_investigation(
            id=inv_id,
            incident_id=incident_id,
            stage=state.status.value,
            state_json=state.model_dump_json(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        inv_repo.close()

        inv_repo2 = InvestigationRepository(tmp_db)
        record = inv_repo2.get_investigation(inv_id)
        loaded = InvestigationState.model_validate_json(record["state_json"])

        assert len(loaded.completed_runs) == 1
        assert loaded.completed_runs[0].id == run_id
        assert loaded.completed_runs[0].agent_name == "log_triage"

        inv_repo2.close()
        incident_repo.close()
