"""Tests for repeated RCA analysis of the same incident.

``POST /api/incidents/{id}/analyze`` used to answer 500 on the second call.
``rca_reports.incident_id`` is UNIQUE, so the re-run updated the existing row and
kept its primary key while the freshly synthesized ``rca.id`` was never inserted;
the proposals that referenced it then tripped
``FOREIGN KEY (rca_id) REFERENCES rca_reports(id)``.

Analysis is now idempotent: an incident that already has an RCA gets the stored
analysis back, so no second proposal set is minted and decisions already recorded
against the current one survive.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.analysis.confidence import ConfidenceEngine, ConfidenceWeights
from backend.app.analysis.contradictions import ContradictionDetector
from backend.app.analysis.rca import RCASynthesisEngine
from backend.app.approval.service import ApprovalService
from backend.app.dependencies import get_rca_service
from backend.app.llm.fake import FakeLLMProvider
from backend.app.main import app
from backend.app.models.approval import ApprovalStatus
from backend.app.remediation.planner import RemediationPlanner
from backend.app.repositories import (
    ApprovalRepository,
    EvidenceRepository,
    FindingRepository,
    IncidentRepository,
    RCARepository,
    RemediationRepository,
)
from backend.app.services.rca_service import RCAService

VALID_RCA_JSON = """{
  "primary_hypothesis": {
    "title": "Deployment regression",
    "explanation": "Recent deployment changed validation behavior",
    "contributing_factors": ["New validation logic"],
    "observed_facts": ["Error rate increased at 14:32 UTC"],
    "inferred_facts": ["Commit 7666d11 is the likely cause"],
    "uncertainties": ["No direct reproduction performed"]
  },
  "alternative_hypotheses": [],
  "observed_facts": ["Error rate increased"],
  "inferred_facts": ["Deployment timing correlates with error onset"],
  "uncertainties": ["No direct reproduction"]
}"""


def build_service(db_path: str, llm: FakeLLMProvider) -> RCAService:
    """Build a real RCAService, wired exactly like get_rca_service but offline."""
    engine = RCASynthesisEngine(
        llm, ConfidenceEngine(ConfidenceWeights()), ContradictionDetector()
    )
    return RCAService(
        incident_repo=IncidentRepository(db_path),
        evidence_repo=EvidenceRepository(db_path),
        finding_repo=FindingRepository(db_path),
        rca_repo=RCARepository(db_path),
        remediation_repo=RemediationRepository(db_path),
        approval_repo=ApprovalRepository(db_path),
        rca_engine=engine,
        remediation_planner=RemediationPlanner(),
        approval_service=ApprovalService(ApprovalRepository(db_path)),
    )


@pytest.fixture()
def offline_llm(tmp_db: str) -> Generator[FakeLLMProvider]:
    """Serve /analyze from a fake LLM so the route can be driven over HTTP.

    ``get_rca_service`` calls ``get_llm_provider()`` directly rather than through
    Depends, so the service itself is the override seam.
    """
    llm = FakeLLMProvider(responses=[VALID_RCA_JSON] * 5)
    app.dependency_overrides[get_rca_service] = lambda: build_service(tmp_db, llm)
    yield llm
    app.dependency_overrides.pop(get_rca_service, None)


def _create_incident(client: TestClient) -> str:
    resp = client.post(
        "/api/incidents",
        json={
            "source": "MANUAL",
            "title": "Analyze endpoint test",
            "severity": "SEV1",
            "service": "payment-service",
            "environment": "production",
            "description": "Negative amounts passing validation",
            "stack_traces": [],
            "raw_payload": {},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _row_count(db_path: str, table: str, incident_id: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE incident_id = ?", (incident_id,)
        ).fetchone()[0]
    finally:
        conn.close()


class TestFirstAnalysis:
    """Unchanged behavior for the first call."""

    def test_synthesizes_and_returns_the_analysis(
        self, client: TestClient, offline_llm: FakeLLMProvider
    ) -> None:
        incident_id = _create_incident(client)

        resp = client.post(f"/api/incidents/{incident_id}/analyze")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["incident_id"] == incident_id
        assert body["rca"]["primary_hypothesis"]["title"] == "Deployment regression"
        assert body["remediation_proposals"] != []
        assert offline_llm.call_count == 1

    def test_unknown_incident_still_returns_404(
        self, client: TestClient, offline_llm: FakeLLMProvider
    ) -> None:
        resp = client.post(f"/api/incidents/{uuid4()}/analyze")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestRepeatedAnalysis:
    """The reported bug: clicking Analyze a second time."""

    def test_second_analyze_returns_200_not_500(
        self, client: TestClient, offline_llm: FakeLLMProvider
    ) -> None:
        incident_id = _create_incident(client)
        first = client.post(f"/api/incidents/{incident_id}/analyze")
        assert first.status_code == 200, first.text

        second = client.post(f"/api/incidents/{incident_id}/analyze")

        assert second.status_code == 200, second.text

    def test_repeated_analyze_returns_the_same_rca(
        self, client: TestClient, offline_llm: FakeLLMProvider
    ) -> None:
        incident_id = _create_incident(client)
        first = client.post(f"/api/incidents/{incident_id}/analyze").json()

        second = client.post(f"/api/incidents/{incident_id}/analyze").json()
        third = client.post(f"/api/incidents/{incident_id}/analyze").json()

        assert second["rca"]["id"] == first["rca"]["id"]
        assert third["rca"]["id"] == first["rca"]["id"]

    def test_repeated_analyze_does_not_re_run_the_llm(
        self, client: TestClient, offline_llm: FakeLLMProvider
    ) -> None:
        incident_id = _create_incident(client)
        client.post(f"/api/incidents/{incident_id}/analyze")

        client.post(f"/api/incidents/{incident_id}/analyze")

        assert offline_llm.call_count == 1

    def test_repeated_analyze_does_not_duplicate_proposals(
        self, client: TestClient, tmp_db: str, offline_llm: FakeLLMProvider
    ) -> None:
        incident_id = _create_incident(client)
        first = client.post(f"/api/incidents/{incident_id}/analyze").json()
        proposal_ids = [p["id"] for p in first["remediation_proposals"]]

        second = client.post(f"/api/incidents/{incident_id}/analyze").json()

        assert [p["id"] for p in second["remediation_proposals"]] == proposal_ids
        assert _row_count(tmp_db, "rca_reports", incident_id) == 1
        assert _row_count(tmp_db, "remediation_proposals", incident_id) == len(proposal_ids)
        assert _row_count(tmp_db, "approvals", incident_id) == len(first["approvals"])

    def test_repeated_analyze_preserves_a_recorded_decision(
        self, client: TestClient, offline_llm: FakeLLMProvider
    ) -> None:
        """A re-analysis must not strand or reset the engineer's decision."""
        incident_id = _create_incident(client)
        first = client.post(f"/api/incidents/{incident_id}/analyze").json()
        remediation_id = first["remediation_proposals"][0]["id"]
        rejected = client.post(
            f"/api/remediations/{remediation_id}/reject?rejected_by=demo-engineer"
        )
        assert rejected.status_code == 200, rejected.text

        second = client.post(f"/api/incidents/{incident_id}/analyze")

        assert second.status_code == 200, second.text
        body = second.json()
        proposal = next(
            p for p in body["remediation_proposals"] if p["id"] == remediation_id
        )
        assert proposal["status"] == "REJECTED"
        assert body["approvals"][0]["status"] == ApprovalStatus.REJECTED.value

        # And the decision is still protected against being made twice.
        again = client.post(
            f"/api/remediations/{remediation_id}/reject?rejected_by=someone-else"
        )
        assert again.status_code == 409

    def test_stored_proposals_reference_a_persisted_rca(
        self, client: TestClient, tmp_db: str, offline_llm: FakeLLMProvider
    ) -> None:
        """The FK the 500 came from: every proposal's rca_id must exist."""
        incident_id = _create_incident(client)
        client.post(f"/api/incidents/{incident_id}/analyze")
        client.post(f"/api/incidents/{incident_id}/analyze")

        conn = sqlite3.connect(tmp_db)
        try:
            orphans = conn.execute(
                """
                SELECT p.id FROM remediation_proposals p
                LEFT JOIN rca_reports r ON r.id = p.rca_id
                WHERE r.id IS NULL
                """
            ).fetchall()
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            conn.close()

        assert orphans == []
        assert violations == []


class TestRCAServiceIdempotency:
    """Service-level contract, independent of the HTTP layer."""

    async def test_second_call_returns_stored_analysis(self, tmp_db: str) -> None:
        incident_id = _seed_incident(tmp_db)
        llm = FakeLLMProvider(responses=[VALID_RCA_JSON] * 3)

        first = await build_service(tmp_db, llm).analyze_incident(incident_id)
        second = await build_service(tmp_db, llm).analyze_incident(incident_id)

        assert second["rca"].id == first["rca"].id
        assert [p.id for p in second["remediation_proposals"]] == [
            p.id for p in first["remediation_proposals"]
        ]
        assert [a.id for a in second["approvals"]] == [a.id for a in first["approvals"]]
        assert llm.call_count == 1

    async def test_second_call_does_not_raise_integrity_error(self, tmp_db: str) -> None:
        incident_id = _seed_incident(tmp_db)
        llm = FakeLLMProvider(responses=[VALID_RCA_JSON] * 3)
        await build_service(tmp_db, llm).analyze_incident(incident_id)

        # Previously: sqlite3.IntegrityError: FOREIGN KEY constraint failed
        await build_service(tmp_db, llm).analyze_incident(incident_id)

    async def test_missing_incident_still_raises_value_error(self, tmp_db: str) -> None:
        llm = FakeLLMProvider(responses=[VALID_RCA_JSON])

        with pytest.raises(ValueError, match="Incident not found"):
            await build_service(tmp_db, llm).analyze_incident(uuid4())


def _seed_incident(db_path: str) -> UUID:
    incident_id = uuid4()
    now = datetime.now(UTC)
    repo = IncidentRepository(db_path)
    try:
        repo.create_incident(
            id=incident_id,
            source="MANUAL",
            title="Analyze idempotency test",
            severity="SEV1",
            service="payment-service",
            environment="production",
            status="INVESTIGATING",
            description="Negative amounts passing validation",
            stack_traces=[],
            created_at=now,
            updated_at=now,
            raw_payload={},
        )
    finally:
        repo.close()
    return incident_id
