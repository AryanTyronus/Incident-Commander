from __future__ import annotations

from backend.app.models.agent_schemas import AgentRunStatus

# Valid state transitions for agent execution
VALID_AGENT_TRANSITIONS: dict[AgentRunStatus, set[AgentRunStatus]] = {
    AgentRunStatus.PENDING: {AgentRunStatus.RUNNING, AgentRunStatus.CANCELLED},
    AgentRunStatus.RUNNING: {
        AgentRunStatus.COMPLETED,
        AgentRunStatus.FAILED,
        AgentRunStatus.CANCELLED,
    },
    AgentRunStatus.COMPLETED: set(),
    AgentRunStatus.FAILED: set(),
    AgentRunStatus.CANCELLED: set(),
}


class InvalidAgentTransitionError(Exception):
    """Raised when an invalid agent status transition is attempted."""

    def __init__(self, current: AgentRunStatus, target: AgentRunStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid agent transition: {current.value} -> {target.value}"
        )


class AgentExecutionStateMachine:
    """Enforces valid status transitions for agent runs."""

    @staticmethod
    def validate_transition(
        current: AgentRunStatus, target: AgentRunStatus
    ) -> None:
        """Validate a status transition.

        Raises:
            InvalidAgentTransitionError: If the transition is not allowed.
        """
        allowed = VALID_AGENT_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise InvalidAgentTransitionError(current, target)

    @staticmethod
    def can_transition(current: AgentRunStatus, target: AgentRunStatus) -> bool:
        """Check if a transition is valid without raising."""
        allowed = VALID_AGENT_TRANSITIONS.get(current, set())
        return target in allowed

    @staticmethod
    def is_terminal(status: AgentRunStatus) -> bool:
        """Check if a status is terminal (no further transitions)."""
        return len(VALID_AGENT_TRANSITIONS.get(status, set())) == 0
