from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.models.rca import (
    ConfidenceBand,
    RootCauseAnalysis,
    RootCauseHypothesis,
    compute_confidence_band,
)


class TestRootCauseHypothesis:
    def test_create_hypothesis(self) -> None:
        h = RootCauseHypothesis(
            title="Deployment regression",
            explanation="Recent deployment changed validation",
            confidence=0.75,
        )
        assert h.title == "Deployment regression"
        assert h.confidence == 0.75
        assert h.id is not None

    def test_confidence_bounds(self) -> None:
        RootCauseHypothesis(
            title="Test",
            explanation="Test",
            confidence=0.0,
        )
        RootCauseHypothesis(
            title="Test",
            explanation="Test",
            confidence=1.0,
        )
        with pytest.raises(Exception):
            RootCauseHypothesis(
                title="Test",
                explanation="Test",
                confidence=-0.1,
            )
        with pytest.raises(Exception):
            RootCauseHypothesis(
                title="Test",
                explanation="Test",
                confidence=1.1,
            )

    def test_evidence_references(self) -> None:
        eid1 = uuid4()
        eid2 = uuid4()
        h = RootCauseHypothesis(
            title="Test",
            explanation="Test",
            confidence=0.5,
            supporting_evidence_ids=[eid1],
            contradicting_evidence_ids=[eid2],
        )
        assert eid1 in h.supporting_evidence_ids
        assert eid2 in h.contradicting_evidence_ids


class TestRootCauseAnalysis:
    def test_create_rca(self) -> None:
        primary = RootCauseHypothesis(
            title="Primary",
            explanation="Primary hypothesis",
            confidence=0.8,
        )
        rca = RootCauseAnalysis(
            incident_id=uuid4(),
            primary_hypothesis=primary,
            confidence=0.75,
            confidence_band="HIGH",
        )
        assert rca.primary_hypothesis.title == "Primary"
        assert rca.confidence == 0.75
        assert rca.confidence_band == "HIGH"

    def test_alternative_hypotheses(self) -> None:
        primary = RootCauseHypothesis(
            title="Primary",
            explanation="Primary",
            confidence=0.8,
        )
        alt = RootCauseHypothesis(
            title="Alternative",
            explanation="Alternative",
            confidence=0.5,
        )
        rca = RootCauseAnalysis(
            incident_id=uuid4(),
            primary_hypothesis=primary,
            alternative_hypotheses=[alt],
            confidence=0.7,
            confidence_band="MEDIUM",
        )
        assert len(rca.alternative_hypotheses) == 1
        assert rca.alternative_hypotheses[0].title == "Alternative"

    def test_facts_classification(self) -> None:
        primary = RootCauseHypothesis(
            title="Test",
            explanation="Test",
            confidence=0.5,
        )
        rca = RootCauseAnalysis(
            incident_id=uuid4(),
            primary_hypothesis=primary,
            confidence=0.5,
            confidence_band="MEDIUM",
            observed_facts=["Error rate increased at 14:32 UTC"],
            inferred_facts=["Commit abc123 is the most likely cause"],
            uncertainties=["No direct reproduction performed"],
        )
        assert len(rca.observed_facts) == 1
        assert len(rca.inferred_facts) == 1
        assert len(rca.uncertainties) == 1


class TestConfidenceBand:
    def test_low(self) -> None:
        assert compute_confidence_band(0.0) == ConfidenceBand.LOW
        assert compute_confidence_band(0.39) == ConfidenceBand.LOW

    def test_medium(self) -> None:
        assert compute_confidence_band(0.40) == ConfidenceBand.MEDIUM
        assert compute_confidence_band(0.69) == ConfidenceBand.MEDIUM

    def test_high(self) -> None:
        assert compute_confidence_band(0.70) == ConfidenceBand.HIGH
        assert compute_confidence_band(0.89) == ConfidenceBand.HIGH

    def test_very_high(self) -> None:
        assert compute_confidence_band(0.90) == ConfidenceBand.VERY_HIGH
        assert compute_confidence_band(1.0) == ConfidenceBand.VERY_HIGH
