from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.analysis.contradictions import ContradictionDetector


class TestContradictionDetector:
    def setup_method(self) -> None:
        self.detector = ContradictionDetector()

    def test_no_contradictions(self) -> None:
        evidence = [
            {"id": uuid4(), "source_type": "LOG", "timestamp": None},
        ]
        findings = [{"confidence": 0.5, "finding_type": "GENERAL"}]
        contradictions = self.detector.analyze(evidence, findings)
        assert len(contradictions) == 0

    def test_finding_contradiction(self) -> None:
        findings = [
            {"agent_name": "agent_a", "confidence": 0.9, "finding_type": "GENERAL"},
            {"agent_name": "agent_b", "confidence": 0.1, "finding_type": "GENERAL"},
        ]
        contradictions = self.detector.analyze([], findings)
        assert len(contradictions) > 0
        assert "agent_a" in contradictions[0].description

    def test_total_impact(self) -> None:
        from backend.app.analysis.contradictions import Contradiction, ContradictionSeverity

        self.detector._contradictions = [
            Contradiction(
                evidence_a_id=uuid4(),
                evidence_b_id=uuid4(),
                description="Test",
                severity=ContradictionSeverity.LOW,
                impact_on_confidence=0.1,
            ),
            Contradiction(
                evidence_a_id=uuid4(),
                evidence_b_id=uuid4(),
                description="Test2",
                severity=ContradictionSeverity.MEDIUM,
                impact_on_confidence=0.2,
            ),
        ]
        assert self.detector.total_impact == pytest.approx(0.3)

    def test_total_impact_capped(self) -> None:
        from backend.app.analysis.contradictions import Contradiction, ContradictionSeverity

        self.detector._contradictions = [
            Contradiction(
                evidence_a_id=uuid4(),
                evidence_b_id=uuid4(),
                description="Test",
                severity=ContradictionSeverity.HIGH,
                impact_on_confidence=0.4,
            ),
            Contradiction(
                evidence_a_id=uuid4(),
                evidence_b_id=uuid4(),
                description="Test2",
                severity=ContradictionSeverity.HIGH,
                impact_on_confidence=0.4,
            ),
        ]
        assert self.detector.total_impact == 0.5  # Capped at 0.5
