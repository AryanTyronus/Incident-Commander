from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest

from backend.app.agents.base import InvestigationContext
from backend.app.agents.commander import (
    IncidentCommander,
)
from backend.app.agents.registry import AgentRegistry
from backend.app.llm.fake import FakeLLMProvider
from backend.app.llm.interface import LLMProviderError
from backend.app.models.agent_schemas import (
    AgentResult,
    InvestigationStage,
)
from backend.app.orchestration.execution import AgentExecutor


class MockAgent:
    """Simple mock agent for testing."""

    def __init__(self, name: str, result: AgentResult | None = None) -> None:
        self.name = name
        self._result = result or AgentResult(
            agent_name=name,
            summary=f"{name} done",
            confidence=0.5,
        )

    async def run(self, context: InvestigationContext) -> AgentResult:
        return self._result


class MockFailingAgent:
    """Mock agent that fails."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, context: InvestigationContext) -> AgentResult:
        raise RuntimeError(f"{self.name} failed")


class FakeAgentRunRepository:
    """In-memory agent run repository for testing."""

    def __init__(self) -> None:
        self._runs: dict[UUID, Any] = {}

    def create_run(self, run: Any) -> Any:
        self._runs[run.id] = run
        return run

    def get_run(self, run_id: UUID) -> Any | None:
        return self._runs.get(run_id)

    def update_run(self, run: Any) -> Any:
        self._runs[run.id] = run
        return run

    def get_runs_for_incident(self, incident_id: UUID) -> list[Any]:
        return [
            r for r in self._runs.values()
            if r.incident_id == incident_id
        ]


class FakeIncidentRepository:
    """Minimal fake incident repository for testing."""

    def __init__(self) -> None:
        self._incidents: dict[UUID, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []

    def add_incident(self, incident: dict[str, Any]) -> None:
        self._incidents[incident["id"]] = incident

    def get_incident(self, incident_id: UUID) -> dict[str, Any] | None:
        return self._incidents.get(incident_id)

    def update_incident_status(
        self, incident_id: UUID, new_status: str
    ) -> dict[str, Any]:
        if incident_id in self._incidents:
            self._incidents[incident_id]["status"] = new_status
        return self._incidents.get(incident_id, {})

    def record_event(self, **kwargs: Any) -> dict[str, Any]:
        self._events.append(kwargs)
        return kwargs


class FakeInvestigationRepository:
    """Minimal fake investigation repository for testing."""

    def __init__(self) -> None:
        self._investigations: dict[UUID, dict[str, Any]] = {}

    def create_investigation(
        self,
        id: UUID,
        incident_id: UUID,
        stage: str,
        state_json: str,
        created_at: Any,
        updated_at: Any,
    ) -> dict[str, Any]:
        record = {
            "id": id,
            "incident_id": incident_id,
            "stage": stage,
            "state_json": state_json,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        self._investigations[id] = record
        return record

    def get_investigation(self, investigation_id: UUID) -> dict[str, Any] | None:
        return self._investigations.get(investigation_id)

    def get_by_incident_id(self, incident_id: UUID) -> dict[str, Any] | None:
        for inv in self._investigations.values():
            if inv["incident_id"] == incident_id:
                return inv
        return None

    def update_investigation(
        self,
        investigation_id: UUID,
        stage: str,
        state_json: str,
        updated_at: Any,
    ) -> dict[str, Any]:
        inv = self._investigations.get(investigation_id)
        if inv:
            inv["stage"] = stage
            inv["state_json"] = state_json
            inv["updated_at"] = updated_at
        return inv or {}


def make_plan_json(tasks: list[dict[str, Any]]) -> str:
    """Helper to create a plan JSON string."""
    return json.dumps({"tasks": tasks})


class TestIncidentCommander:
    """Tests for IncidentCommander."""

    def setup_method(self) -> None:
        self.run_repo = FakeAgentRunRepository()
        self.incident_repo = FakeIncidentRepository()
        self.investigation_repo = FakeInvestigationRepository()
        self.executor = AgentExecutor(self.run_repo)
        self.registry = AgentRegistry()

    def _make_commander(
        self,
        llm: FakeLLMProvider,
        registry: AgentRegistry | None = None,
    ) -> IncidentCommander:
        return IncidentCommander(
            llm=llm,
            repo=self.incident_repo,
            agent_run_repo=self.run_repo,
            investigation_repo=self.investigation_repo,
            executor=self.executor,
            registry=registry or self.registry,
        )

    def _add_incident(self, incident_id: UUID) -> None:
        self.incident_repo.add_incident({
            "id": incident_id,
            "title": "Test Incident",
            "severity": "SEV1",
            "service": "test-service",
            "environment": "production",
            "status": "RECEIVED",
            "description": "A test incident",
        })

    async def test_investigate_unknown_incident(self) -> None:
        llm = FakeLLMProvider(responses=[make_plan_json([])])
        commander = self._make_commander(llm)

        with pytest.raises(Exception):
            await commander.investigate(uuid4())

    async def test_investigate_builds_plan(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)

        plan_response = make_plan_json([
            {
                "agent_name": "log_triage",
                "purpose": "Check logs",
                "priority": 1,
                "input": {},
            }
        ])
        llm = FakeLLMProvider(responses=[plan_response])
        self.registry.register(MockAgent("log_triage"))

        commander = self._make_commander(llm)
        state = await commander.investigate(incident_id)

        assert state.status == InvestigationStage.COMPLETED
        assert llm.call_count == 1

    async def test_investigate_malformed_llm_response(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)

        llm = FakeLLMProvider(responses=["not valid json {{{"])
        commander = self._make_commander(llm)
        state = await commander.investigate(incident_id)

        assert state.status == InvestigationStage.FAILED
        assert any(
            "invalid json" in e.lower() or "jsondecodeerror" in e.lower()
            for e in state.errors
        )

    async def test_investigate_unknown_agent_rejected(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)

        plan_response = make_plan_json([
            {
                "agent_name": "unknown_agent",
                "purpose": "Do something",
                "priority": 1,
                "input": {},
            }
        ])
        llm = FakeLLMProvider(responses=[plan_response])
        commander = self._make_commander(llm)

        state = await commander.investigate(incident_id)

        assert state.status == InvestigationStage.FAILED
        assert any("unknown_agent" in e for e in state.errors)

    async def test_investigate_successful_agents(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)

        plan_response = make_plan_json([
            {"agent_name": "agent_a", "purpose": "Task A", "priority": 1, "input": {}},
            {"agent_name": "agent_b", "purpose": "Task B", "priority": 2, "input": {}},
        ])
        llm = FakeLLMProvider(responses=[plan_response])

        self.registry.register(MockAgent("agent_a"))
        self.registry.register(MockAgent("agent_b"))

        commander = self._make_commander(llm)
        state = await commander.investigate(incident_id)

        assert state.status == InvestigationStage.COMPLETED
        assert len(state.completed_runs) == 2
        assert len(state.failed_runs) == 0

    async def test_investigate_mixed_success_failure(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)

        plan_response = make_plan_json([
            {"agent_name": "good_agent", "purpose": "Succeed", "priority": 1, "input": {}},
            {"agent_name": "bad_agent", "purpose": "Fail", "priority": 2, "input": {}},
        ])
        llm = FakeLLMProvider(responses=[plan_response])

        self.registry.register(MockAgent("good_agent"))
        self.registry.register(MockFailingAgent("bad_agent"))

        commander = self._make_commander(llm)
        state = await commander.investigate(incident_id)

        assert state.status == InvestigationStage.COMPLETED
        assert len(state.completed_runs) == 1
        assert len(state.failed_runs) == 1

    async def test_investigate_llm_failure(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)

        llm = FakeLLMProvider(error=LLMProviderError("LLM down"))
        commander = self._make_commander(llm)
        state = await commander.investigate(incident_id)

        assert state.status == InvestigationStage.FAILED
        assert len(state.errors) > 0

    async def test_investigate_records_events(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)

        plan_response = make_plan_json([
            {"agent_name": "agent_a", "purpose": "Task", "priority": 1, "input": {}},
        ])
        llm = FakeLLMProvider(responses=[plan_response])
        self.registry.register(MockAgent("agent_a"))

        commander = self._make_commander(llm)
        await commander.investigate(incident_id)

        event_types = [e["event_type"] for e in self.incident_repo._events]
        assert "INVESTIGATION_STARTED" in event_types
        assert "PLAN_CREATED" in event_types
        assert "AGENT_COMPLETED" in event_types
        assert "INVESTIGATION_COMPLETED" in event_types

    async def test_investigate_transitions_incident_status(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)

        plan_response = make_plan_json([])
        llm = FakeLLMProvider(responses=[plan_response])

        commander = self._make_commander(llm)
        await commander.investigate(incident_id)

        incident = self.incident_repo.get_incident(incident_id)
        assert incident is not None
        assert incident["status"] == "INVESTIGATING"

    async def test_get_state(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)

        plan_response = make_plan_json([])
        llm = FakeLLMProvider(responses=[plan_response])

        commander = self._make_commander(llm)
        await commander.investigate(incident_id)

        state = commander.get_state(incident_id)
        assert state is not None
        assert state.incident_id == incident_id
