from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.models.evidence import Evidence, SourceType
from backend.app.models.findings import AgentFinding, FindingType


class TestEvidenceModel:
    """Tests for the Evidence model."""

    def test_create_evidence(self) -> None:
        evidence = Evidence(
            incident_id=uuid4(),
            source_type=SourceType.LOG,
            source_reference="/var/log/app.log",
            content="Error count: 50",
        )
        assert evidence.id is not None
        assert evidence.source_type == SourceType.LOG
        assert evidence.source_reference == "/var/log/app.log"
        assert evidence.content == "Error count: 50"
        assert evidence.created_at is not None

    def test_source_reference_required(self) -> None:
        with pytest.raises(Exception):
            Evidence(
                incident_id=uuid4(),
                source_type=SourceType.LOG,
                source_reference="",
                content="test",
            )

    def test_source_reference_whitespace_rejected(self) -> None:
        with pytest.raises(Exception):
            Evidence(
                incident_id=uuid4(),
                source_type=SourceType.LOG,
                source_reference="   ",
                content="test",
            )

    def test_source_types(self) -> None:
        for st in SourceType:
            evidence = Evidence(
                incident_id=uuid4(),
                source_type=st,
                source_reference="test-ref",
                content="test content",
            )
            assert evidence.source_type == st

    def test_metadata_round_trip(self) -> None:
        evidence = Evidence(
            incident_id=uuid4(),
            source_type=SourceType.GIT_COMMIT,
            source_reference="abc123",
            content="commit message",
            metadata={"key": "value", "count": 42},
        )
        dumped = evidence.model_dump()
        loaded = Evidence.model_validate(dumped)
        assert loaded.metadata == {"key": "value", "count": 42}

    def test_timestamp_optional(self) -> None:
        evidence = Evidence(
            incident_id=uuid4(),
            source_type=SourceType.LOG,
            source_reference="test",
            content="content",
        )
        assert evidence.timestamp is None

    def test_source_reference_stripped(self) -> None:
        evidence = Evidence(
            incident_id=uuid4(),
            source_type=SourceType.LOG,
            source_reference="  /var/log/app.log  ",
            content="content",
        )
        assert evidence.source_reference == "/var/log/app.log"


class TestAgentFindingModel:
    """Tests for the AgentFinding model."""

    def test_create_finding(self) -> None:
        finding = AgentFinding(
            incident_id=uuid4(),
            agent_name="log_triage",
            finding_type=FindingType.LOG_ANOMALY,
            summary="50 errors detected",
            confidence=0.75,
        )
        assert finding.id is not None
        assert finding.agent_name == "log_triage"
        assert finding.confidence == 0.75

    def test_confidence_validation(self) -> None:
        with pytest.raises(Exception):
            AgentFinding(
                incident_id=uuid4(),
                agent_name="test",
                finding_type=FindingType.GENERAL,
                summary="test",
                confidence=1.5,
            )

        with pytest.raises(Exception):
            AgentFinding(
                incident_id=uuid4(),
                agent_name="test",
                finding_type=FindingType.GENERAL,
                summary="test",
                confidence=-0.1,
            )

    def test_summary_required(self) -> None:
        with pytest.raises(Exception):
            AgentFinding(
                incident_id=uuid4(),
                agent_name="test",
                finding_type=FindingType.GENERAL,
                summary="",
                confidence=0.5,
            )

    def test_evidence_ids(self) -> None:
        eid1 = uuid4()
        eid2 = uuid4()
        finding = AgentFinding(
            incident_id=uuid4(),
            agent_name="test",
            finding_type=FindingType.LOG_ANOMALY,
            summary="test finding",
            confidence=0.5,
            evidence_ids=[eid1, eid2],
        )
        assert len(finding.evidence_ids) == 2
        assert eid1 in finding.evidence_ids
        assert eid2 in finding.evidence_ids

    def test_finding_types(self) -> None:
        for ft in FindingType:
            finding = AgentFinding(
                incident_id=uuid4(),
                agent_name="test",
                finding_type=ft,
                summary="test",
                confidence=0.5,
            )
            assert finding.finding_type == ft

    def test_metadata_round_trip(self) -> None:
        finding = AgentFinding(
            incident_id=uuid4(),
            agent_name="test",
            finding_type=FindingType.GENERAL,
            summary="test",
            confidence=0.5,
            metadata={"error_count": 10},
        )
        dumped = finding.model_dump()
        loaded = AgentFinding.model_validate(dumped)
        assert loaded.metadata == {"error_count": 10}
