from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from backend.app.config import settings
from backend.app.events.model import EventType
from backend.app.events.publisher import event_publisher
from backend.app.models.agent_schemas import InvestigationStage, InvestigationState
from backend.app.repositories import (
    AgentRunRepository,
    EvidenceRepository,
    FindingRepository,
    IncidentRepository,
    InvestigationRepository,
)
from backend.app.retrieval.chroma import ChromaRetrieval
from backend.app.retrieval.embeddings import FakeEmbeddingProvider
from backend.app.tools.runbook_search import RunbookSearch

logger = logging.getLogger(__name__)

#: Stages that mean an investigation is still in flight.
ACTIVE_STAGES: frozenset[str] = frozenset(
    {
        InvestigationStage.PLANNING.value,
        InvestigationStage.EXECUTING.value,
        InvestigationStage.AGGREGATING.value,
    }
)


def build_commander(
    *,
    repo: IncidentRepository,
    db_path: str,
    llm: Any | None = None,
    agent_run_repo: Any | None = None,
    investigation_repo: InvestigationRepository | None = None,
) -> Any:
    """Wire an IncidentCommander with the registered investigation agents.

    Shared by the request-scoped FastAPI dependency and by the background
    runner, so both paths always execute the identical agent set. Agent imports
    stay local to keep the retrieval stack out of application startup.
    """
    from backend.app.agents.commander import IncidentCommander
    from backend.app.agents.git_forensics import GitForensicsAgent
    from backend.app.agents.log_triage import LogTriageAgent
    from backend.app.agents.registry import AgentRegistry
    from backend.app.agents.runbook import RunbookAgent
    from backend.app.orchestration.execution import AgentExecutor

    if llm is None:
        from backend.app.llm.ollama import OllamaProvider

        llm = OllamaProvider()

    runs_repo = agent_run_repo if agent_run_repo is not None else AgentRunRepository(db_path)
    investigations = (
        investigation_repo if investigation_repo is not None else InvestigationRepository(db_path)
    )
    evidence_repo = EvidenceRepository(db_path)
    finding_repo = FindingRepository(db_path)
    repo_root = Path(db_path).resolve().parent.parent
    runbook_dir = Path(settings.RUNBOOK_DIRECTORY)
    if not runbook_dir.exists():
        runbook_dir = repo_root / "fixtures" / "runbooks"
    retrieval = ChromaRetrieval(
        embedding_provider=FakeEmbeddingProvider(),
        persist_directory=settings.CHROMA_PERSIST_DIRECTORY,
    )
    runbook_search = RunbookSearch(retrieval)
    if retrieval.count() == 0 and runbook_dir.exists():
        runbook_search.index_runbooks(runbook_dir)

    registry = AgentRegistry()
    registry.register(LogTriageAgent(evidence_repo, finding_repo))
    registry.register(GitForensicsAgent(evidence_repo, finding_repo))
    registry.register(RunbookAgent(evidence_repo, finding_repo, runbook_search))

    return IncidentCommander(
        llm=llm,
        repo=repo,
        agent_run_repo=runs_repo,
        investigation_repo=investigations,
        executor=AgentExecutor(runs_repo),
        registry=registry,
    )


class InvestigationRunner:
    """Executes investigations outside the HTTP request/response cycle.

    ``POST /api/incidents/{id}/investigate`` validates the incident, schedules
    :meth:`run` as a Starlette background task and answers 202 immediately; an
    investigation takes minutes of LLM and agent work, far longer than a request
    should be held open. Progress reaches the browser over the incident
    WebSocket instead.

    The runner owns its database connections rather than reusing the request's:
    FastAPI closes ``yield`` dependencies before background tasks run, so the
    request-scoped connection is already closed by the time :meth:`run` starts.
    """

    def __init__(
        self,
        *,
        db_path: str | None = None,
        commander_factory: Callable[[IncidentRepository], Any] | None = None,
    ) -> None:
        self._db_path = db_path or settings.DATABASE_PATH
        self._commander_factory = commander_factory

    async def run(self, incident_id: UUID) -> None:
        """Run one full investigation.

        Deliberately raises nothing: a background task has no caller left to
        handle an exception, so every failure is logged and persisted instead.
        """
        from backend.app.agents.commander import InvestigationAlreadyRunningError

        repo = IncidentRepository(self._db_path)
        try:
            commander = (
                self._commander_factory(repo)
                if self._commander_factory is not None
                else build_commander(repo=repo, db_path=self._db_path)
            )
            await commander.investigate(incident_id)
        except InvestigationAlreadyRunningError:
            # A concurrent caller won the race and owns the investigation state;
            # overwriting it with a failure would abort a healthy run.
            logger.info("Investigation already running for %s; skipping", incident_id)
        except Exception as e:
            # IncidentCommander records failures raised inside its own pipeline.
            # Reaching here means it could not start at all, so the failure is
            # persisted on its behalf - otherwise the UI waits forever.
            logger.exception("Background investigation failed for %s", incident_id)
            self._record_failure(repo, incident_id, e)
        finally:
            repo.close()

    def _record_failure(
        self, repo: IncidentRepository, incident_id: UUID, error: Exception
    ) -> None:
        """Persist, audit and stream a failure the commander could not report."""
        message = f"{type(error).__name__}: {error}"
        payload = {"error": message}

        self._persist_failed_state(incident_id, message)

        try:
            repo.record_event(
                id=uuid4(),
                incident_id=incident_id,
                event_type=EventType.INVESTIGATION_FAILED.value,
                old_status=None,
                new_status=None,
                payload=payload,
                created_at=datetime.now(UTC),
            )
        except Exception:
            logger.exception("Could not write failure event for %s", incident_id)

        try:
            event_publisher.publish(
                incident_id=incident_id,
                event_type=EventType.INVESTIGATION_FAILED,
                payload=payload,
            )
        except Exception:
            logger.exception("Could not stream failure event for %s", incident_id)

    def _persist_failed_state(self, incident_id: UUID, message: str) -> None:
        """Record a FAILED investigation state so the UI stops waiting."""
        state = InvestigationState(
            incident_id=incident_id,
            status=InvestigationStage.FAILED,
            current_stage=InvestigationStage.FAILED,
            errors=[message],
        )
        now = datetime.now(UTC)

        investigation_repo = InvestigationRepository(self._db_path)
        try:
            existing = investigation_repo.get_by_incident_id(incident_id)
            if existing is None:
                investigation_repo.create_investigation(
                    id=uuid4(),
                    incident_id=incident_id,
                    stage=state.status.value,
                    state_json=state.model_dump_json(),
                    created_at=now,
                    updated_at=now,
                )
            else:
                investigation_repo.update_investigation(
                    investigation_id=existing["id"],
                    stage=state.status.value,
                    state_json=state.model_dump_json(),
                    updated_at=now,
                )
        except Exception:
            logger.exception("Could not persist failed state for %s", incident_id)
        finally:
            investigation_repo.close()
