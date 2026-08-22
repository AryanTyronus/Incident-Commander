from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import Depends

from backend.app.approval.service import ApprovalService
from backend.app.config import settings
from backend.app.repositories import (
    AgentRunRepository,
    ApprovalRepository,
    EvidenceRepository,
    FindingRepository,
    IncidentRepository,
    InvestigationRepository,
    RCARepository,
    RemediationRepository,
)
from backend.app.services.incident_service import IncidentService
from backend.app.services.rca_service import RCAService


def get_db_connection() -> sqlite3.Connection:  # type: ignore[misc]
    """FastAPI dependency that provides a database connection."""
    from backend.app.db import get_connection, initialize_database

    conn = get_connection(settings.DATABASE_PATH)
    initialize_database(conn)
    try:
        yield conn
    finally:
        conn.close()


def get_repository(
    conn: Annotated[sqlite3.Connection, Depends(get_db_connection)],
) -> IncidentRepository:
    """FastAPI dependency that provides an IncidentRepository."""
    repo = IncidentRepository.__new__(IncidentRepository)
    repo._conn = conn
    repo._db_path = settings.DATABASE_PATH
    return repo


def get_incident_service(
    repo: Annotated[IncidentRepository, Depends(get_repository)],
) -> IncidentService:
    """FastAPI dependency that provides an IncidentService."""
    return IncidentService(repo)


def get_agent_run_repo() -> AgentRunRepository:
    """FastAPI dependency that provides an AgentRunRepository."""
    return AgentRunRepository(settings.DATABASE_PATH)


def get_investigation_repo() -> InvestigationRepository:
    """FastAPI dependency that provides an InvestigationRepository."""
    return InvestigationRepository(settings.DATABASE_PATH)


def get_evidence_repo() -> EvidenceRepository:
    """FastAPI dependency that provides an EvidenceRepository."""
    return EvidenceRepository(settings.DATABASE_PATH)


def get_finding_repo() -> FindingRepository:
    """FastAPI dependency that provides a FindingRepository."""
    return FindingRepository(settings.DATABASE_PATH)


def get_llm_provider():
    """FastAPI dependency that provides an LLM provider.

    In production, returns OllamaProvider.
    In tests, can be overridden with FakeLLMProvider.
    """
    from backend.app.llm.ollama import OllamaProvider
    return OllamaProvider()


def get_commander(
    llm: Annotated[object, Depends(get_llm_provider)],
    repo: Annotated[IncidentRepository, Depends(get_repository)],
    agent_run_repo: Annotated[AgentRunRepository, Depends(get_agent_run_repo)],
    investigation_repo: Annotated[InvestigationRepository, Depends(get_investigation_repo)],
):
    """FastAPI dependency that provides an IncidentCommander with Phase 3 agents."""
    from backend.app.services.investigation_runner import build_commander

    return build_commander(
        repo=repo,
        db_path=settings.DATABASE_PATH,
        llm=llm,
        agent_run_repo=agent_run_repo,
        investigation_repo=investigation_repo,
    )


def get_investigation_runner():
    """FastAPI dependency that provides the background InvestigationRunner.

    Kept as a dependency rather than a module-level singleton so tests can
    substitute a runner through ``app.dependency_overrides``.
    """
    from backend.app.services.investigation_runner import InvestigationRunner

    return InvestigationRunner(db_path=settings.DATABASE_PATH)


# Type aliases for route signatures
RepositoryDep = Annotated[IncidentRepository, Depends(get_repository)]
ServiceDep = Annotated[IncidentService, Depends(get_incident_service)]
AgentRunRepoDep = Annotated[AgentRunRepository, Depends(get_agent_run_repo)]
InvestigationRepoDep = Annotated[InvestigationRepository, Depends(get_investigation_repo)]
EvidenceRepoDep = Annotated[EvidenceRepository, Depends(get_evidence_repo)]
FindingRepoDep = Annotated[FindingRepository, Depends(get_finding_repo)]
CommanderDep = Annotated[object, Depends(get_commander)]
InvestigationRunnerDep = Annotated[object, Depends(get_investigation_runner)]


# Phase 4 dependencies
def get_rca_repo() -> RCARepository:
    """FastAPI dependency that provides an RCARepository."""
    return RCARepository(settings.DATABASE_PATH)


def get_remediation_repo() -> RemediationRepository:
    """FastAPI dependency that provides a RemediationRepository."""
    return RemediationRepository(settings.DATABASE_PATH)


def get_approval_repo() -> ApprovalRepository:
    """FastAPI dependency that provides an ApprovalRepository."""
    return ApprovalRepository(settings.DATABASE_PATH)


def get_rca_service(
    repo: Annotated[IncidentRepository, Depends(get_repository)],
    evidence_repo: Annotated[EvidenceRepository, Depends(get_evidence_repo)],
    finding_repo: Annotated[FindingRepository, Depends(get_finding_repo)],
    rca_repo: Annotated[RCARepository, Depends(get_rca_repo)],
    remediation_repo: Annotated[RemediationRepository, Depends(get_remediation_repo)],
    approval_repo: Annotated[ApprovalRepository, Depends(get_approval_repo)],
):
    """FastAPI dependency that provides an RCAService."""
    from backend.app.analysis.confidence import ConfidenceEngine, ConfidenceWeights
    from backend.app.analysis.contradictions import ContradictionDetector
    from backend.app.analysis.rca import RCASynthesisEngine
    from backend.app.remediation.planner import RemediationPlanner

    weights = ConfidenceWeights(
        support_weight=settings.RCA_SUPPORT_WEIGHT,
        temporal_weight=settings.RCA_TEMPORAL_WEIGHT,
        correlation_weight=settings.RCA_CORRELATION_WEIGHT,
        documentation_weight=settings.RCA_DOCUMENTATION_WEIGHT,
        contradiction_penalty=settings.RCA_CONTRADICTION_PENALTY,
        missing_data_penalty=settings.RCA_MISSING_DATA_PENALTY,
    )

    llm = get_llm_provider()
    confidence_engine = ConfidenceEngine(weights)
    contradiction_detector = ContradictionDetector()
    rca_engine = RCASynthesisEngine(llm, confidence_engine, contradiction_detector)
    remediation_planner = RemediationPlanner()
    approval_service = ApprovalService(approval_repo)

    return RCAService(
        incident_repo=repo,
        evidence_repo=evidence_repo,
        finding_repo=finding_repo,
        rca_repo=rca_repo,
        remediation_repo=remediation_repo,
        approval_repo=approval_repo,
        rca_engine=rca_engine,
        remediation_planner=remediation_planner,
        approval_service=approval_service,
    )


def get_approval_service(
    approval_repo: Annotated[ApprovalRepository, Depends(get_approval_repo)],
):
    """FastAPI dependency that provides an ApprovalService."""
    return ApprovalService(approval_repo)


RCAServiceDep = Annotated[RCAService, Depends(get_rca_service)]
ApprovalServiceDep = Annotated[ApprovalService, Depends(get_approval_service)]
RCADep = Annotated[RCARepository, Depends(get_rca_repo)]
RemediationRepoDep = Annotated[RemediationRepository, Depends(get_remediation_repo)]
ApprovalRepoDep = Annotated[ApprovalRepository, Depends(get_approval_repo)]
