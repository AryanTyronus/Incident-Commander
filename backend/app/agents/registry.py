from __future__ import annotations

from backend.app.agents.base import BaseAgent


class AgentRegistry:
    """Registry of available investigation agents.

    Agents are registered by name. The commander looks up agents by name
    when executing investigation plans.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent by its name attribute."""
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        """Retrieve an agent by name."""
        return self._agents.get(name)

    def has(self, name: str) -> bool:
        """Check if an agent is registered."""
        return name in self._agents

    def list_agents(self) -> list[str]:
        """Return names of all registered agents."""
        return list(self._agents.keys())
