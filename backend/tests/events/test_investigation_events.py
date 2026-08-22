"""Tests that investigation lifecycle events reach the existing event stream.

The commander has always written events to the SQLite audit trail. It now also
publishes them through ``EventPublisher``, which is what the incident WebSocket
broadcasts, so the browser can watch a background investigation progress.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from backend.app.agents.commander import IncidentCommander
from backend.app.agents.registry import AgentRegistry
from backend.app.dependencies import get_investigation_runner
from backend.app.events.model import EventType, IncidentEvent
from backend.app.events.publisher import event_publisher
from backend.app.llm.fake import FakeLLMProvider
from backend.app.llm.interface import LLMProviderError
from backend.app.main import app
from backend.app.models.agent_schemas import InvestigationStage
from backend.app.orchestration.execution import AgentExecutor
from backend.app.repositories import (
    AgentRunRepository,
    IncidentRepository,
    InvestigationRepository,
)
from backend.app.services.investigation_runner import InvestigationRunner
from backend.tests.test_commander import (
    FakeAgentRunRepository,
    FakeIncidentRepository,
    FakeInvestigationRepository,
    MockAgent,
    MockFailingAgent,
    make_plan_json,
)


class _Capture:
    """Collect every event published for one incident."""

    def __init__(self, incident_id: UUID) -> None:
        self._incident_id = incident_id
        self.events: list[IncidentEvent] = []

    def __enter__(self) -> list[IncidentEvent]:
        event_publisher.subscribe(self._incident_id, self.events.append)
        return self.events

    def __exit__(self, *exc: object) -> None:
        event_publisher.unsubscribe(self._incident_id, self.events.append)


class TestInvestigationLifecycleEvents:
    """Every stage of an investigation must be observable on the stream."""

    def setup_method(self) -> None:
        self.incident_repo = FakeIncidentRepository()
        self.run_repo = FakeAgentRunRepository()
        self.investigation_repo = FakeInvestigationRepository()
        self.registry = AgentRegistry()

    def _commander(self, llm: FakeLLMProvider) -> IncidentCommander:
        return IncidentCommander(
            llm=llm,
            repo=self.incident_repo,
            agent_run_repo=self.run_repo,
            investigation_repo=self.investigation_repo,
            executor=AgentExecutor(self.run_repo),
            registry=self.registry,
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

    async def test_successful_investigation_publishes_every_stage(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)
        self.registry.register(MockAgent("log_triage"))
        llm = FakeLLMProvider(
            responses=[make_plan_json([
                {"agent_name": "log_triage", "purpose": "check logs", "priority": 10},
            ])]
        )

        with _Capture(incident_id) as published:
            state = await self._commander(llm).investigate(incident_id)

        assert state.status == InvestigationStage.COMPLETED
        types = [e.event_type for e in published]
        for expected in (
            EventType.INVESTIGATION_STARTED,
            EventType.INVESTIGATION_STAGE_CHANGED,
            EventType.PLAN_CREATED,
            EventType.AGENT_STARTED,
            EventType.AGENT_COMPLETED,
            EventType.INVESTIGATION_COMPLETED,
        ):
            assert expected in types, f"{expected} was not published"

    async def test_stage_changes_cover_the_whole_progression(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)
        self.registry.register(MockAgent("log_triage"))
        llm = FakeLLMProvider(
            responses=[make_plan_json([
                {"agent_name": "log_triage", "purpose": "check logs", "priority": 10},
            ])]
        )

        with _Capture(incident_id) as published:
            await self._commander(llm).investigate(incident_id)

        stages = [
            e.payload["stage"]
            for e in published
            if e.event_type == EventType.INVESTIGATION_STAGE_CHANGED
        ]
        assert stages == ["PLANNING", "EXECUTING", "AGGREGATING", "COMPLETED"]

    async def test_agent_events_carry_the_agent_name(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)
        self.registry.register(MockAgent("log_triage"))
        llm = FakeLLMProvider(
            responses=[make_plan_json([
                {"agent_name": "log_triage", "purpose": "check logs", "priority": 10},
            ])]
        )

        with _Capture(incident_id) as published:
            await self._commander(llm).investigate(incident_id)

        agent_events = [
            e
            for e in published
            if e.event_type in (EventType.AGENT_STARTED, EventType.AGENT_COMPLETED)
        ]
        assert agent_events
        assert all(e.agent_name == "log_triage" for e in agent_events)

    async def test_agent_failure_is_published(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)
        self.registry.register(MockFailingAgent("log_triage"))
        llm = FakeLLMProvider(
            responses=[make_plan_json([
                {"agent_name": "log_triage", "purpose": "check logs", "priority": 10},
            ])]
        )

        with _Capture(incident_id) as published:
            await self._commander(llm).investigate(incident_id)

        types = [e.event_type for e in published]
        assert EventType.AGENT_STARTED in types
        assert EventType.AGENT_FAILED in types

    async def test_investigation_failure_is_published(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)
        llm = FakeLLMProvider(error=LLMProviderError("ollama down"))

        with _Capture(incident_id) as published:
            state = await self._commander(llm).investigate(incident_id)

        assert state.status == InvestigationStage.FAILED
        assert EventType.INVESTIGATION_FAILED in [e.event_type for e in published]

    async def test_sequences_are_monotonic(self) -> None:
        """The frontend drops events whose sequence does not advance."""
        incident_id = uuid4()
        self._add_incident(incident_id)
        self.registry.register(MockAgent("log_triage"))
        llm = FakeLLMProvider(
            responses=[make_plan_json([
                {"agent_name": "log_triage", "purpose": "check logs", "priority": 10},
            ])]
        )

        with _Capture(incident_id) as published:
            await self._commander(llm).investigate(incident_id)

        sequences = [e.sequence for e in published]
        assert sequences == sorted(sequences)
        assert len(set(sequences)) == len(sequences)

    async def test_audit_trail_is_still_written(self) -> None:
        """Streaming is additive: SQLite remains the source of truth."""
        incident_id = uuid4()
        self._add_incident(incident_id)
        self.registry.register(MockAgent("log_triage"))
        llm = FakeLLMProvider(
            responses=[make_plan_json([
                {"agent_name": "log_triage", "purpose": "check logs", "priority": 10},
            ])]
        )

        await self._commander(llm).investigate(incident_id)

        recorded = [e["event_type"] for e in self.incident_repo._events]
        assert "INVESTIGATION_STARTED" in recorded
        assert "INVESTIGATION_STAGE_CHANGED" in recorded
        assert "AGENT_STARTED" in recorded
        assert "AGENT_COMPLETED" in recorded
        assert "INVESTIGATION_COMPLETED" in recorded

    async def test_unstreamed_event_type_is_audited_without_raising(self) -> None:
        """An audit-only event type must not break the investigation."""
        incident_id = uuid4()
        self._add_incident(incident_id)
        commander = self._commander(FakeLLMProvider(responses=[]))

        with _Capture(incident_id) as published:
            commander._record_event(incident_id, "SOMETHING_INTERNAL", {})

        assert published == []
        assert self.incident_repo._events[-1]["event_type"] == "SOMETHING_INTERNAL"

    async def test_subscriber_failure_does_not_abort_the_investigation(self) -> None:
        incident_id = uuid4()
        self._add_incident(incident_id)
        self.registry.register(MockAgent("log_triage"))
        llm = FakeLLMProvider(
            responses=[make_plan_json([
                {"agent_name": "log_triage", "purpose": "check logs", "priority": 10},
            ])]
        )

        def broken(event: IncidentEvent) -> None:
            raise RuntimeError("subscriber exploded")

        event_publisher.subscribe(incident_id, broken)
        try:
            state = await self._commander(llm).investigate(incident_id)
        finally:
            event_publisher.unsubscribe(incident_id, broken)

        assert state.status == InvestigationStage.COMPLETED


class TestEventsReachTheWebSocket:
    """End-to-end: background investigation -> publisher -> WebSocket client."""

    def test_background_investigation_streams_events_to_a_connected_client(
        self, client: TestClient, tmp_db: str
    ) -> None:
        incident_id = _create_incident(client)

        def commander_factory(repo: IncidentRepository) -> IncidentCommander:
            """A real commander on real repositories, with a fake LLM and agent."""
            registry = AgentRegistry()
            registry.register(MockAgent("log_triage"))
            run_repo = AgentRunRepository(tmp_db)
            return IncidentCommander(
                llm=FakeLLMProvider(
                    responses=[make_plan_json([
                        {"agent_name": "log_triage", "purpose": "logs", "priority": 10},
                    ])]
                ),
                repo=repo,
                agent_run_repo=run_repo,
                investigation_repo=InvestigationRepository(tmp_db),
                executor=AgentExecutor(run_repo),
                registry=registry,
            )

        runner = InvestigationRunner(db_path=tmp_db, commander_factory=commander_factory)
        app.dependency_overrides[get_investigation_runner] = lambda: runner
        try:
            with client.websocket_connect(f"/api/incidents/{incident_id}/stream") as ws:
                resp = client.post(f"/api/incidents/{incident_id}/investigate")
                assert resp.status_code == 202

                received = [ws.receive_json() for _ in range(4)]
        finally:
            app.dependency_overrides.pop(get_investigation_runner, None)

        types = [e["event_type"] for e in received]
        assert EventType.INVESTIGATION_STARTED.value in types
        assert EventType.INVESTIGATION_STAGE_CHANGED.value in types
        assert all(e["incident_id"] == incident_id for e in received)
        assert [e["sequence"] for e in received] == sorted(e["sequence"] for e in received)

        # The investigation ran to completion in the background.
        state = client.get(f"/api/incidents/{incident_id}/investigation").json()
        assert state["stage"] == InvestigationStage.COMPLETED.value


def _create_incident(client: TestClient) -> str:
    resp = client.post(
        "/api/incidents",
        json={
            "source": "MANUAL",
            "title": "Stream test incident",
            "severity": "SEV2",
            "service": "payment-service",
            "environment": "production",
            "description": "Event stream test",
            "stack_traces": [],
            "raw_payload": {},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]
