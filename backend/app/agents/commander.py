from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.app.agents.base import InvestigationContext
from backend.app.agents.prompts import (
    INVESTIGATION_PLAN_SYSTEM_PROMPT,
    INVESTIGATION_PLAN_USER_PROMPT,
)
from backend.app.agents.registry import AgentRegistry
from backend.app.events.model import EventType
from backend.app.events.publisher import event_publisher
from backend.app.llm.interface import LLMProvider, LLMProviderError
from backend.app.models.agent_schemas import (
    AgentResult,
    AgentRun,
    AgentRunStatus,
    InvestigationPlan,
    InvestigationStage,
    InvestigationState,
    InvestigationTask,
)
from backend.app.orchestration.execution import AgentExecutor
from backend.app.repositories import IncidentRepository, InvestigationRepository

logger = logging.getLogger(__name__)


class PlanningError(Exception):
    """Raised when investigation planning fails."""


class UnknownAgentError(Exception):
    """Raised when the planner suggests an unknown agent."""


class InvestigationAlreadyRunningError(Exception):
    """Raised when an investigation is already in progress."""


class IncidentCommander:
    """Orchestrates incident investigation using agents.

    Responsibilities:
    1. Accept an incident.
    2. Build an investigation plan (using LLM).
    3. Execute agents (potentially in parallel).
    4. Aggregate results.
    5. Update investigation state.
    6. Persist investigation state to SQLite.
    """

    def __init__(
        self,
        *,
        llm: LLMProvider,
        repo: IncidentRepository,
        agent_run_repo: Any,
        investigation_repo: InvestigationRepository,
        executor: AgentExecutor,
        registry: AgentRegistry,
    ) -> None:
        self._llm = llm
        self._repo = repo
        self._agent_run_repo = agent_run_repo
        self._investigation_repo = investigation_repo
        self._executor = executor
        self._registry = registry
        self._states: dict[UUID, InvestigationState] = {}

    async def investigate(self, incident_id: UUID) -> InvestigationState:
        """Start an investigation for the given incident.

        Args:
            incident_id: The incident to investigate.

        Returns:
            The final InvestigationState.

        Raises:
            InvestigationAlreadyRunningError: If already investigating.
            PlanningError: If the LLM fails to produce a valid plan.
            UnknownAgentError: If the plan references unknown agents.
        """
        # Load incident
        incident = self._repo.get_incident(incident_id)
        if incident is None:
            from backend.app.services.incident_service import IncidentNotFoundError
            raise IncidentNotFoundError(incident_id)

        # Check if already investigating (in-memory or persisted)
        existing = self._load_state(incident_id)
        if existing and existing.status in (
            InvestigationStage.PLANNING,
            InvestigationStage.EXECUTING,
            InvestigationStage.AGGREGATING,
        ):
            raise InvestigationAlreadyRunningError(
                f"Investigation already running for {incident_id}"
            )

        # Initialize state
        state = InvestigationState(
            incident_id=incident_id,
            status=InvestigationStage.PLANNING,
            current_stage=InvestigationStage.PLANNING,
        )
        self._persist_state(incident_id, state)

        # Record investigation started
        self._record_event(
            incident_id,
            "INVESTIGATION_STARTED",
            {},
        )

        # Transition to INVESTIGATING
        self._repo.update_incident_status(incident_id, "INVESTIGATING")

        try:
            # Build plan
            plan = await self._build_plan(incident)
            state.status = InvestigationStage.EXECUTING
            state.current_stage = InvestigationStage.EXECUTING
            self._persist_state(incident_id, state)

            self._record_event(
                incident_id,
                "PLAN_CREATED",
                {"task_count": len(plan.tasks)},
            )

            # Execute agents
            await self._execute_plan(plan, state)

            # Aggregate results
            state.status = InvestigationStage.AGGREGATING
            state.current_stage = InvestigationStage.AGGREGATING
            # ``AgentRun.output`` holds the JSON-serialisable dict the executor
            # stored (``AgentResult.model_dump()``), while ``findings`` is typed
            # ``list[AgentResult]``. Rebuild the models rather than dropping the
            # dicts in: appending to a list field skips validation, so the
            # mismatch would only surface as a serializer warning on persist.
            state.findings = [
                AgentResult.model_validate(run.output)
                for run in state.completed_runs
                if run.output is not None
            ]
            self._persist_state(incident_id, state)

            # Complete
            state.status = InvestigationStage.COMPLETED
            state.current_stage = InvestigationStage.COMPLETED
            self._persist_state(incident_id, state)

            self._record_event(
                incident_id,
                "INVESTIGATION_COMPLETED",
                {
                    "completed": len(state.completed_runs),
                    "failed": len(state.failed_runs),
                },
            )

            logger.info(
                "Investigation completed for incident %s: "
                "%d completed, %d failed",
                incident_id,
                len(state.completed_runs),
                len(state.failed_runs),
            )

        except Exception as e:
            state.status = InvestigationStage.FAILED
            state.current_stage = InvestigationStage.FAILED
            state.errors.append(f"{type(e).__name__}: {e}")
            self._persist_state(incident_id, state)

            self._record_event(
                incident_id,
                "INVESTIGATION_FAILED",
                {"error": str(e)},
            )

            logger.error(
                "Investigation failed for incident %s: %s",
                incident_id,
                e,
            )

        return state

    async def _build_plan(self, incident: dict[str, Any]) -> InvestigationPlan:
        """Use the LLM to generate an investigation plan."""
        user_prompt = INVESTIGATION_PLAN_USER_PROMPT.format(
            title=incident["title"],
            severity=incident["severity"],
            service=incident["service"],
            environment=incident["environment"],
            description=incident.get("description", ""),
        )

        try:
            response = await self._llm.generate(
                user_prompt,
                system_prompt=INVESTIGATION_PLAN_SYSTEM_PROMPT,
            )
        except LLMProviderError as e:
            raise PlanningError(f"LLM failed to generate plan: {e}") from e

        # Parse and validate
        plan = self._parse_plan(response, incident["id"])

        # Validate all agent names
        for task in plan.tasks:
            if not self._registry.has(task.agent_name):
                raise UnknownAgentError(
                    f"Unknown agent '{task.agent_name}'. "
                    f"Available: {self._registry.list_agents()}"
                )

        return plan

    def _parse_plan(self, llm_output: str, incident_id: UUID) -> InvestigationPlan:
        """Parse LLM output into a validated InvestigationPlan."""
        # Extract JSON from the response
        text = llm_output.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise PlanningError(
                f"LLM returned invalid JSON: {e}"
            ) from e

        if not isinstance(data, dict) or "tasks" not in data:
            raise PlanningError(
                "LLM response missing required 'tasks' field"
            )

        tasks = []
        for task_data in data["tasks"]:
            tasks.append(InvestigationTask(
                agent_name=task_data.get("agent_name", ""),
                purpose=task_data.get("purpose", ""),
                priority=task_data.get("priority", 50),
                input=task_data.get("input", {}),
            ))

        return InvestigationPlan(
            incident_id=incident_id,
            tasks=tasks,
        )

    async def _execute_plan(
        self, plan: InvestigationPlan, state: InvestigationState
    ) -> None:
        """Execute all tasks in the plan concurrently."""
        import asyncio

        incident = self._repo.get_incident(plan.incident_id) or {}
        extra_context = {
            **(incident.get("raw_payload") or {}),
        }
        if incident.get("stack_traces"):
            extra_context.setdefault("stack_trace", incident["stack_traces"][0])
        if incident.get("service"):
            extra_context.setdefault("service", incident["service"])

        async def run_task(task: InvestigationTask) -> None:
            agent = self._registry.get(task.agent_name)
            if agent is None:
                # Should not happen after validation, but be safe
                state.errors.append(f"Agent not found: {task.agent_name}")
                return

            context = InvestigationContext(
                incident_id=plan.incident_id,
                incident=incident,
                state=state,
                extra={**extra_context, **task.input},
            )

            self._record_event(
                plan.incident_id,
                "AGENT_STARTED",
                {"agent_name": task.agent_name, "purpose": task.purpose},
            )

            run = await self._executor.execute(
                incident_id=plan.incident_id,
                agent_name=task.agent_name,
                agent=agent,
                context=context,
                input_data=task.input,
            )

            if run.status == AgentRunStatus.COMPLETED:
                state.active_runs = [
                    r for r in state.active_runs if r.id != run.id
                ]
                state.completed_runs.append(run)
                self._record_event(
                    plan.incident_id,
                    "AGENT_COMPLETED",
                    {"agent_name": task.agent_name, "run_id": str(run.id)},
                )
            else:
                state.active_runs = [
                    r for r in state.active_runs if r.id != run.id
                ]
                state.failed_runs.append(run)
                if run.error:
                    state.errors.append(run.error)
                self._record_event(
                    plan.incident_id,
                    "AGENT_FAILED",
                    {
                        "agent_name": task.agent_name,
                        "run_id": str(run.id),
                        "error": run.error,
                    },
                )

        # Create pending runs for tracking
        for task in plan.tasks:
            pending_run = AgentRun(
                id=uuid4(),
                incident_id=plan.incident_id,
                agent_name=task.agent_name,
                status=AgentRunStatus.PENDING,
            )
            state.active_runs.append(pending_run)

        # Execute all tasks concurrently
        await asyncio.gather(*[run_task(task) for task in plan.tasks])

    def _record_event(
        self,
        incident_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Record an investigation event in the audit trail and stream it."""
        self._repo.record_event(
            id=uuid4(),
            incident_id=incident_id,
            event_type=event_type,
            old_status=None,
            new_status=None,
            payload=payload,
            created_at=datetime.now(UTC),
        )
        self._publish_event(incident_id, event_type, payload)

    @staticmethod
    def _publish_event(
        incident_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Fan an audit event out to live WebSocket subscribers.

        SQLite is the source of truth; streaming is best-effort, so neither an
        unrecognised event type nor a subscriber error may abort the
        investigation that produced it.
        """
        try:
            streamed_type = EventType(event_type)
        except ValueError:
            logger.debug("Event %s is audit-only; not streamed", event_type)
            return

        try:
            event_publisher.publish(
                incident_id=incident_id,
                event_type=streamed_type,
                agent_name=payload.get("agent_name"),
                payload=payload,
            )
        except Exception as e:
            logger.warning("Failed to stream event %s: %s", event_type, e)

    def _persist_state(self, incident_id: UUID, state: InvestigationState) -> None:
        """Persist investigation state to SQLite."""
        now = datetime.now(UTC)
        state_json = state.model_dump_json()

        existing = self._investigation_repo.get_by_incident_id(incident_id)
        if existing is None:
            self._investigation_repo.create_investigation(
                id=uuid4(),
                incident_id=incident_id,
                stage=state.status.value,
                state_json=state_json,
                created_at=now,
                updated_at=now,
            )
        else:
            self._investigation_repo.update_investigation(
                investigation_id=existing["id"],
                stage=state.status.value,
                state_json=state_json,
                updated_at=now,
            )

        # Update in-memory cache
        self._states[incident_id] = state

        # Record stage change event
        self._record_event(
            incident_id,
            "INVESTIGATION_STAGE_CHANGED",
            {"stage": state.status.value},
        )

    def _load_state(self, incident_id: UUID) -> InvestigationState | None:
        """Load investigation state from persistence or memory cache."""
        # Check in-memory cache first
        if incident_id in self._states:
            return self._states[incident_id]

        # Load from persistence
        record = self._investigation_repo.get_by_incident_id(incident_id)
        if record is None:
            return None

        state = InvestigationState.model_validate_json(record["state_json"])
        # Update in-memory cache
        self._states[incident_id] = state
        return state

    def get_state(self, incident_id: UUID) -> InvestigationState | None:
        """Get the current investigation state for an incident."""
        return self._load_state(incident_id)
