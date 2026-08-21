from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.app.models.agent_schemas import AgentRun, AgentRunStatus
from backend.app.orchestration.state_machine import (
    AgentExecutionStateMachine,
    InvalidAgentTransitionError,
)

logger = logging.getLogger(__name__)


class AgentExecutionError(Exception):
    """Raised when agent execution fails."""


class AgentExecutor:
    """Executes agent runs with proper state management and persistence.

    Responsibilities:
    1. Create AgentRun records.
    2. Manage status transitions.
    3. Execute agents.
    4. Capture results and errors.
    5. Persist state through the repository.
    """

    def __init__(self, agent_run_repo: Any) -> None:
        self._repo = agent_run_repo
        self._state_machine = AgentExecutionStateMachine()

    async def execute(
        self,
        *,
        incident_id: Any,
        agent_name: str,
        agent: Any,
        context: Any,
        input_data: dict[str, Any] | None = None,
    ) -> AgentRun:
        """Execute an agent and return the completed run record.

        Args:
            incident_id: The incident being investigated.
            agent_name: Name of the agent to execute.
            agent: The agent instance (must have a run() method).
            context: InvestigationContext for the agent.
            input_data: Optional input data for the agent.

        Returns:
            The AgentRun record after execution.
        """
        now = datetime.now(UTC)
        run = AgentRun(
            id=uuid4(),
            incident_id=incident_id,
            agent_name=agent_name,
            status=AgentRunStatus.PENDING,
            input=input_data or {},
            metadata={"started_by": "executor"},
        )

        # Persist initial PENDING state
        run = self._repo.create_run(run)

        try:
            # Transition to RUNNING
            run = self._transition(run, AgentRunStatus.RUNNING, now)

            # Execute the agent
            logger.info(
                "Agent %s started for incident %s",
                agent_name,
                incident_id,
            )

            result = await agent.run(context)

            # Transition to COMPLETED
            now_complete = datetime.now(UTC)
            run = self._transition(run, AgentRunStatus.COMPLETED, now_complete)
            run.output = result.model_dump()
            run.completed_at = now_complete

            logger.info(
                "Agent %s completed for incident %s",
                agent_name,
                incident_id,
            )

        except Exception as e:
            # Transition to FAILED
            now_fail = datetime.now(UTC)
            run = self._transition(run, AgentRunStatus.FAILED, now_fail)
            run.error = f"{type(e).__name__}: {e}"
            run.completed_at = now_fail

            logger.error(
                "Agent %s failed for incident %s: %s",
                agent_name,
                incident_id,
                run.error,
            )

        # Persist final state
        run = self._repo.update_run(run)
        return run

    def _transition(
        self, run: AgentRun, target: AgentRunStatus, now: datetime
    ) -> AgentRun:
        """Attempt a status transition on the run."""
        try:
            self._state_machine.validate_transition(run.status, target)
        except InvalidAgentTransitionError:
            logger.error(
                "Invalid transition %s -> %s for run %s",
                run.status.value,
                target.value,
                run.id,
            )
            raise

        run.status = target
        if target == AgentRunStatus.RUNNING:
            run.started_at = now
        return run
