from __future__ import annotations

from uuid import uuid4

from backend.app.models.rca import RootCauseAnalysis, RootCauseHypothesis
from backend.app.remediation.rollback import RollbackPlanner


class TestRollbackPlanner:
    def setup_method(self) -> None:
        self.planner = RollbackPlanner()

    def test_no_git_evidence(self) -> None:
        rca = RootCauseAnalysis(
            incident_id=uuid4(),
            primary_hypothesis=RootCauseHypothesis(
                title="Test", explanation="Test", confidence=0.5,
            ),
            confidence=0.5,
            confidence_band="MEDIUM",
        )
        evidence = [{"id": uuid4(), "source_type": "LOG"}]
        result = self.planner.generate(rca, evidence)
        assert result is None

    def test_with_git_evidence(self) -> None:
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
                "metadata": {"commit_hash": "abc123def456"},
            },
        ]
        result = self.planner.generate(rca, evidence)
        assert result is not None
        assert "abc123d" in result.title
        assert len(result.commands) > 0
        assert "git revert" in result.commands[0]
        assert result.requires_approval is True
