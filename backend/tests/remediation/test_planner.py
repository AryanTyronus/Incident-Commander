from __future__ import annotations

from uuid import uuid4

from backend.app.models.rca import RootCauseAnalysis, RootCauseHypothesis
from backend.app.models.remediation import RemediationStatus, RemediationType
from backend.app.remediation.planner import RemediationPlanner


class TestRemediationPlanner:
    def setup_method(self) -> None:
        self.planner = RemediationPlanner()

    def test_investigation_proposal_when_no_evidence(self) -> None:
        rca = RootCauseAnalysis(
            incident_id=uuid4(),
            primary_hypothesis=RootCauseHypothesis(
                title="Test", explanation="Test", confidence=0.3,
            ),
            confidence=0.3,
            confidence_band="LOW",
        )
        proposals = self.planner.generate_proposals(rca, [])
        assert len(proposals) == 1
        assert proposals[0].type == RemediationType.INVESTIGATION
        assert proposals[0].requires_approval is True

    def test_rollback_proposal(self) -> None:
        rca = RootCauseAnalysis(
            incident_id=uuid4(),
            primary_hypothesis=RootCauseHypothesis(
                title="Test", explanation="Test", confidence=0.5,
            ),
            confidence=0.5,
            confidence_band="MEDIUM",
        )
        evidence = [
            {
                "id": uuid4(),
                "source_type": "GIT_COMMIT",
                "metadata": {"commit_hash": "abc123"},
            },
        ]
        proposals = self.planner.generate_proposals(rca, evidence)
        types = [p.type for p in proposals]
        assert RemediationType.ROLLBACK in types

    def test_all_proposals_require_approval(self) -> None:
        rca = RootCauseAnalysis(
            incident_id=uuid4(),
            primary_hypothesis=RootCauseHypothesis(
                title="Test", explanation="Test", confidence=0.5,
            ),
            confidence=0.5,
            confidence_band="MEDIUM",
        )
        proposals = self.planner.generate_proposals(rca, [])
        for p in proposals:
            assert p.requires_approval is True
            assert p.status == RemediationStatus.PROPOSED
