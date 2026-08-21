from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from backend.app.models.agent_schemas import AgentResult, InvestigationState


@dataclass
class InvestigationContext:
    """Context provided to agents during investigation."""

    incident_id: UUID
    incident: dict[str, Any]
    state: InvestigationState
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class BaseAgent(Protocol):
    """Protocol that all investigation agents must implement.

    Phase 3 agents (LogTriageAgent, GitForensicsAgent, RunbookAgent)
    will implement this interface.
    """

    name: str

    async def run(self, context: InvestigationContext) -> AgentResult:
        """Execute the agent's investigation logic.

        Args:
            context: The investigation context.

        Returns:
            An AgentResult with findings and confidence.
        """
        ...
