from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.app.agents.base import InvestigationContext
from backend.app.agents.runbook import RunbookAgent
from backend.app.models.agent_schemas import InvestigationState
from backend.app.models.evidence import SourceType
from backend.app.repositories import (
    EvidenceRepository,
    FindingRepository,
    IncidentRepository,
)
from backend.app.retrieval.chroma import ChromaRetrieval
from backend.app.retrieval.embeddings import FakeEmbeddingProvider
from backend.app.tools.runbook_search import RunbookSearch

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures"


def _create_test_incident(repo: IncidentRepository, incident_id: uuid4) -> dict:
    """Create a test incident to satisfy FK constraints."""
    return repo.create_incident(
        id=incident_id,
        source="MANUAL",
        title="Test Incident",
        severity="SEV1",
        service="test-service",
        environment="production",
        status="RECEIVED",
        description="Test incident",
        stack_traces=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        raw_payload={},
    )


class TestRunbookAgent:
    """Tests for the RunbookAgent."""

    def setup_method(self) -> None:
        self.db_path = tempfile.mktemp(suffix=".db")
        self.incident_repo = IncidentRepository(self.db_path)
        self.evidence_repo = EvidenceRepository(self.db_path)
        self.finding_repo = FindingRepository(self.db_path)
        self.chroma_dir = tempfile.mkdtemp()
        self.provider = FakeEmbeddingProvider()
        self.retrieval = ChromaRetrieval(
            embedding_provider=self.provider,
            collection_name="test_runbooks",
            persist_directory=self.chroma_dir,
        )
        self.search = RunbookSearch(self.retrieval)

        runbooks_dir = FIXTURES_DIR / "runbooks"
        if runbooks_dir.exists():
            self.search.index_runbooks(runbooks_dir)

    def teardown_method(self) -> None:
        self.incident_repo.close()
        self.evidence_repo.close()
        self.finding_repo.close()
        Path(self.db_path).unlink(missing_ok=True)

    def _make_context(
        self, incident_id: uuid4, **extra
    ) -> InvestigationContext:
        state = InvestigationState(incident_id=incident_id)
        return InvestigationContext(
            incident_id=incident_id,
            incident={
                "service": "payment-service",
                "title": "Payment failures",
            },
            state=state,
            extra=extra,
        )

    async def test_search_runbooks(self) -> None:
        agent = RunbookAgent(
            self.evidence_repo, self.finding_repo, self.search
        )
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        context = self._make_context(incident_id)

        result = await agent.run(context)

        assert result.agent_name == "runbook"
        assert result.confidence > 0.1
        assert result.findings is not None
        assert len(result.findings) > 0

    async def test_runbook_evidence_persisted(self) -> None:
        agent = RunbookAgent(
            self.evidence_repo, self.finding_repo, self.search
        )
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        context = self._make_context(incident_id)

        await agent.run(context)

        evidence = self.evidence_repo.list_for_incident(incident_id)
        runbook_evidence = [
            e for e in evidence if e["source_type"] == SourceType.RUNBOOK.value
        ]
        assert len(runbook_evidence) > 0

    async def test_no_search_configured(self) -> None:
        agent = RunbookAgent(self.evidence_repo, self.finding_repo)
        incident_id = uuid4()
        context = self._make_context(incident_id)

        result = await agent.run(context)
        assert result.confidence == 0.0
        assert "not configured" in result.summary.lower()

    async def test_no_relevant_documents(self) -> None:
        empty_provider = FakeEmbeddingProvider()
        empty_retrieval = ChromaRetrieval(
            embedding_provider=empty_provider,
            collection_name="empty_test",
            persist_directory=tempfile.mkdtemp(),
        )
        empty_search = RunbookSearch(empty_retrieval)

        agent = RunbookAgent(
            self.evidence_repo, self.finding_repo, empty_search
        )
        incident_id = uuid4()
        _create_test_incident(self.incident_repo, incident_id)
        context = self._make_context(incident_id)

        result = await agent.run(context)

        assert result.confidence < 0.3
