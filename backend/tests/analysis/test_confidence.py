from __future__ import annotations

from backend.app.analysis.confidence import ConfidenceEngine, ConfidenceWeights


class TestConfidenceEngine:
    def setup_method(self) -> None:
        self.engine = ConfidenceEngine()

    def test_no_data(self) -> None:
        score = self.engine.calculate([], [], [])
        assert score.total == 0.0

    def test_with_findings(self) -> None:
        findings = [
            {
                "confidence": 0.8,
                "evidence_ids": ["e1"],
                "finding_type": "LOG_ANOMALY",
            },
            {
                "confidence": 0.6,
                "evidence_ids": ["e2"],
                "finding_type": "CANDIDATE_CHANGE",
            },
        ]
        evidence = [
            {"id": "e1", "source_type": "LOG"},
            {"id": "e2", "source_type": "GIT_COMMIT"},
        ]
        score = self.engine.calculate(findings, evidence, [])
        assert score.total > 0.0
        assert score.support_score > 0.0

    def test_with_contradictions(self) -> None:
        from uuid import uuid4

        from backend.app.analysis.contradictions import Contradiction, ContradictionSeverity

        findings = [{"confidence": 0.8, "evidence_ids": [], "finding_type": "GENERAL"}]
        evidence = [{"id": uuid4(), "source_type": "LOG"}]
        contradictions = [
            Contradiction(
                evidence_a_id=uuid4(),
                evidence_b_id=uuid4(),
                description="Test contradiction",
                severity=ContradictionSeverity.HIGH,
                impact_on_confidence=0.2,
            )
        ]
        score = self.engine.calculate(findings, evidence, contradictions)
        assert score.contradiction_penalty > 0.0

    def test_confidence_bounds(self) -> None:
        findings = [{"confidence": 1.0, "evidence_ids": [], "finding_type": "GENERAL"}]
        evidence = [{"id": "e1", "source_type": "LOG"}]
        score = self.engine.calculate(findings, evidence, [])
        assert 0.0 <= score.total <= 1.0

    def test_custom_weights(self) -> None:
        weights = ConfidenceWeights(
            support_weight=0.5,
            temporal_weight=0.1,
            correlation_weight=0.1,
            documentation_weight=0.1,
            contradiction_penalty=0.1,
            missing_data_penalty=0.1,
        )
        engine = ConfidenceEngine(weights)
        findings = [{"confidence": 0.8, "evidence_ids": [], "finding_type": "GENERAL"}]
        evidence = [{"id": "e1", "source_type": "LOG"}]
        score = engine.calculate(findings, evidence, [])
        assert 0.0 <= score.total <= 1.0
