from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from backend.app.agents.base import InvestigationContext
from backend.app.llm.interface import LLMProvider
from backend.app.models.agent_schemas import AgentResult, AgentRun
from backend.app.repositories import AgentRunRepository

logger = logging.getLogger(__name__)


class DummyAgent:
    """A minimal test agent that implements BaseAgent protocol."""

    def __init__(self, name: str = "dummy") -> None:
        self.name = name

    async def run(self, context: InvestigationContext) -> AgentResult:
        """Return a placeholder result."""
        return AgentResult(
            agent_name=self.name,
            summary=f"Dummy agent {self.name} executed",
            findings=[{"type": "placeholder", "data": "no real analysis"}],
            confidence=0.5,
        )


class AgentService:
    """Service layer for agent operations."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        agent_run_repo: AgentRunRepository,
        incident_repo: Any,
    ) -> None:
        self._llm = llm
        self._agent_run_repo = agent_run_repo
        self._incident_repo = incident_repo

    def get_agent_runs(self, incident_id: UUID) -> list[dict[str, Any]]:
        """Get all agent runs for an incident."""
        runs = self._agent_run_repo.get_runs_for_incident(incident_id)
        return [self._run_to_dict(r) for r in runs]

    def get_agent_run(self, run_id: UUID) -> dict[str, Any] | None:
        """Get a specific agent run."""
        run = self._agent_run_repo.get_run(run_id)
        if run is None:
            return None
        return self._run_to_dict(run)

    @staticmethod
    def _run_to_dict(run: AgentRun) -> dict[str, Any]:
        """Convert an AgentRun to a dictionary."""
        return run.model_dump(mode="json")
