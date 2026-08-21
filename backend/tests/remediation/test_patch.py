from __future__ import annotations

from uuid import uuid4

from backend.app.models.rca import RootCauseAnalysis, RootCauseHypothesis
from backend.app.remediation.patch import PatchPlanner


class TestPatchPlanner:
    def setup_method(self) -> None:
        self.planner = PatchPlanner()

    def test_no_diff_evidence(self) -> None:
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

    def test_with_diff_evidence(self) -> None:
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
                "source_type": "GIT_DIFF",
                "metadata": {"files_changed": ["payment/service.py", "tests/test_payment.py"]},
                "content": "+++ payment/service.py\n+++ tests/test_payment.py",
            },
        ]
        result = self.planner.generate(rca, evidence)
        assert result is not None
        assert "payment/service.py" in result.patch_summary
        assert result.requires_approval is True
        assert len(result.commands) == 0  # Patch proposals don't have commands
