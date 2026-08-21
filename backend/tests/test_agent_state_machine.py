from __future__ import annotations

import pytest

from backend.app.models.agent_schemas import AgentRunStatus
from backend.app.orchestration.state_machine import (
    AgentExecutionStateMachine,
    InvalidAgentTransitionError,
)


class TestAgentExecutionStateMachine:
    """Tests for agent execution state transitions."""

    def setup_method(self) -> None:
        self.sm = AgentExecutionStateMachine()

    def test_pending_to_running(self) -> None:
        self.sm.validate_transition(AgentRunStatus.PENDING, AgentRunStatus.RUNNING)

    def test_running_to_completed(self) -> None:
        self.sm.validate_transition(AgentRunStatus.RUNNING, AgentRunStatus.COMPLETED)

    def test_running_to_failed(self) -> None:
        self.sm.validate_transition(AgentRunStatus.RUNNING, AgentRunStatus.FAILED)

    def test_pending_to_cancelled(self) -> None:
        self.sm.validate_transition(AgentRunStatus.PENDING, AgentRunStatus.CANCELLED)

    def test_running_to_cancelled(self) -> None:
        self.sm.validate_transition(AgentRunStatus.RUNNING, AgentRunStatus.CANCELLED)

    def test_invalid_completed_to_running(self) -> None:
        with pytest.raises(InvalidAgentTransitionError):
            self.sm.validate_transition(AgentRunStatus.COMPLETED, AgentRunStatus.RUNNING)

    def test_invalid_completed_to_failed(self) -> None:
        with pytest.raises(InvalidAgentTransitionError):
            self.sm.validate_transition(AgentRunStatus.COMPLETED, AgentRunStatus.FAILED)

    def test_invalid_failed_to_running(self) -> None:
        with pytest.raises(InvalidAgentTransitionError):
            self.sm.validate_transition(AgentRunStatus.FAILED, AgentRunStatus.RUNNING)

    def test_invalid_cancelled_to_running(self) -> None:
        with pytest.raises(InvalidAgentTransitionError):
            self.sm.validate_transition(AgentRunStatus.CANCELLED, AgentRunStatus.RUNNING)

    def test_invalid_pending_to_completed(self) -> None:
        with pytest.raises(InvalidAgentTransitionError):
            self.sm.validate_transition(AgentRunStatus.PENDING, AgentRunStatus.COMPLETED)

    def test_invalid_pending_to_failed(self) -> None:
        with pytest.raises(InvalidAgentTransitionError):
            self.sm.validate_transition(AgentRunStatus.PENDING, AgentRunStatus.FAILED)

    def test_can_transition_valid(self) -> None:
        assert self.sm.can_transition(AgentRunStatus.PENDING, AgentRunStatus.RUNNING)

    def test_can_transition_invalid(self) -> None:
        assert not self.sm.can_transition(AgentRunStatus.COMPLETED, AgentRunStatus.RUNNING)

    def test_is_terminal_completed(self) -> None:
        assert self.sm.is_terminal(AgentRunStatus.COMPLETED)

    def test_is_terminal_failed(self) -> None:
        assert self.sm.is_terminal(AgentRunStatus.FAILED)

    def test_is_terminal_cancelled(self) -> None:
        assert self.sm.is_terminal(AgentRunStatus.CANCELLED)

    def test_is_not_terminal_pending(self) -> None:
        assert not self.sm.is_terminal(AgentRunStatus.PENDING)

    def test_is_not_terminal_running(self) -> None:
        assert not self.sm.is_terminal(AgentRunStatus.RUNNING)

    def test_invalid_transition_error_message(self) -> None:
        with pytest.raises(InvalidAgentTransitionError, match="COMPLETED -> RUNNING"):
            self.sm.validate_transition(AgentRunStatus.COMPLETED, AgentRunStatus.RUNNING)
