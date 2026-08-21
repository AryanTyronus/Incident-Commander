from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from backend.app.agents.base import InvestigationContext
from backend.app.models.agent_schemas import (
    AgentResult,
    AgentRun,
    AgentRunStatus,
    InvestigationState,
)
from backend.app.orchestration.execution import AgentExecutor


class SuccessfulAgent:
    """Test agent that succeeds."""

    def __init__(self, name: str = "test_agent") -> None:
        self.name = name

    async def run(self, context: InvestigationContext) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            summary="Investigation complete",
            findings=[{"type": "test", "data": "finding1"}],
            confidence=0.85,
        )


class FailingAgent:
    """Test agent that raises an exception."""

    def __init__(self, name: str = "failing_agent") -> None:
        self.name = name

    async def run(self, context: InvestigationContext) -> AgentResult:
        raise RuntimeError("Agent crashed")


class SlowAgent:
    """Test agent with controlled delay."""

    def __init__(self, name: str, event: asyncio.Event) -> None:
        self.name = name
        self._event = event

    async def run(self, context: InvestigationContext) -> AgentResult:
        await self._event.wait()
        return AgentResult(
            agent_name=self.name,
            summary=f"{self.name} completed",
            confidence=0.7,
        )


class FakeAgentRunRepository:
    """In-memory agent run repository for testing."""

    def __init__(self) -> None:
        self._runs: dict[UUID, AgentRun] = {}

    def create_run(self, run: AgentRun) -> AgentRun:
        self._runs[run.id] = run
        return run

    def get_run(self, run_id: UUID) -> AgentRun | None:
        return self._runs.get(run_id)

    def update_run(self, run: AgentRun) -> AgentRun:
        self._runs[run.id] = run
        return run

    def get_runs_for_incident(self, incident_id: UUID) -> list[AgentRun]:
        return [
            r for r in self._runs.values()
            if r.incident_id == incident_id
        ]


class TestAgentExecutor:
    """Tests for AgentExecutor."""

    async def test_successful_execution(self) -> None:
        repo = FakeAgentRunRepository()
        executor = AgentExecutor(repo)
        agent = SuccessfulAgent()
        incident_id = uuid4()

        context = InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=InvestigationState(incident_id=incident_id),
        )

        run = await executor.execute(
            incident_id=incident_id,
            agent_name="test_agent",
            agent=agent,
            context=context,
        )

        assert run.status == AgentRunStatus.COMPLETED
        assert run.output is not None
        assert run.output["agent_name"] == "test_agent"
        assert run.output["summary"] == "Investigation complete"
        assert run.completed_at is not None
        assert run.error is None

    async def test_failed_execution(self) -> None:
        repo = FakeAgentRunRepository()
        executor = AgentExecutor(repo)
        agent = FailingAgent()
        incident_id = uuid4()

        context = InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=InvestigationState(incident_id=incident_id),
        )

        run = await executor.execute(
            incident_id=incident_id,
            agent_name="failing_agent",
            agent=agent,
            context=context,
        )

        assert run.status == AgentRunStatus.FAILED
        assert run.error is not None
        assert "RuntimeError" in run.error
        assert run.completed_at is not None

    async def test_run_persisted(self) -> None:
        repo = FakeAgentRunRepository()
        executor = AgentExecutor(repo)
        agent = SuccessfulAgent()
        incident_id = uuid4()

        context = InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=InvestigationState(incident_id=incident_id),
        )

        run = await executor.execute(
            incident_id=incident_id,
            agent_name="test_agent",
            agent=agent,
            context=context,
        )

        # Verify persisted
        persisted = repo.get_run(run.id)
        assert persisted is not None
        assert persisted.status == AgentRunStatus.COMPLETED

    async def test_run_with_input(self) -> None:
        repo = FakeAgentRunRepository()
        executor = AgentExecutor(repo)
        agent = SuccessfulAgent()
        incident_id = uuid4()

        context = InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=InvestigationState(incident_id=incident_id),
        )

        run = await executor.execute(
            incident_id=incident_id,
            agent_name="test_agent",
            agent=agent,
            context=context,
            input_data={"key": "value"},
        )

        assert run.input == {"key": "value"}

    async def test_concurrent_execution(self) -> None:
        """Test that multiple agents can run concurrently."""
        repo = FakeAgentRunRepository()
        executor = AgentExecutor(repo)

        event_a = asyncio.Event()
        event_b = asyncio.Event()

        agent_a = SlowAgent("agent_a", event_a)
        agent_b = SlowAgent("agent_b", event_b)

        incident_id = uuid4()
        context_a = InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=InvestigationState(incident_id=incident_id),
        )
        context_b = InvestigationContext(
            incident_id=incident_id,
            incident={},
            state=InvestigationState(incident_id=incident_id),
        )

        # Start both concurrently
        task_a = asyncio.create_task(
            executor.execute(
                incident_id=incident_id,
                agent_name="agent_a",
                agent=agent_a,
                context=context_a,
            )
        )
        task_b = asyncio.create_task(
            executor.execute(
                incident_id=incident_id,
                agent_name="agent_b",
                agent=agent_b,
                context=context_b,
            )
        )

        # Both should be waiting
        await asyncio.sleep(0.01)
        assert not task_a.done()
        assert not task_b.done()

        # Release both
        event_a.set()
        event_b.set()

        run_a, run_b = await asyncio.gather(task_a, task_b)

        assert run_a.status == AgentRunStatus.COMPLETED
        assert run_b.status == AgentRunStatus.COMPLETED
        assert run_a.agent_name == "agent_a"
        assert run_b.agent_name == "agent_b"
