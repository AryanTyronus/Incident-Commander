from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from backend.app.models.rca import RootCauseAnalysis
from backend.app.models.remediation import (
    RemediationProposal,
    RemediationStatus,
    RemediationType,
)
from backend.app.remediation.patch import PatchPlanner
from backend.app.remediation.rollback import RollbackPlanner
from backend.app.remediation.safety import SafetyValidator, SafetyViolation

logger = logging.getLogger(__name__)


class RemediationPlanner:
    """Generates remediation proposals from RCA.

    Does NOT execute anything. Only generates proposals.
    """

    def __init__(
        self,
        rollback_planner: RollbackPlanner | None = None,
        patch_planner: PatchPlanner | None = None,
        safety_validator: SafetyValidator | None = None,
    ) -> None:
        self._rollback_planner = rollback_planner or RollbackPlanner()
        self._patch_planner = patch_planner or PatchPlanner()
        self._safety_validator = safety_validator or SafetyValidator()

    def generate_proposals(
        self,
        rca: RootCauseAnalysis,
        evidence_items: list[dict[str, Any]],
    ) -> list[RemediationProposal]:
        """Generate remediation proposals from RCA.

        Returns a list of proposals. All proposals require approval.
        """
        proposals = []

        # Try rollback
        rollback = self._rollback_planner.generate(rca, evidence_items)
        if rollback:
            proposals.append(rollback)

        # Try patch
        patch = self._patch_planner.generate(rca, evidence_items)
        if patch:
            proposals.append(patch)

        # If no specific proposal, generate investigation proposal
        if not proposals:
            proposals.append(self._create_investigation_proposal(rca))

        # Validate safety of all proposals
        validated_proposals = []
        for proposal in proposals:
            try:
                self._safety_validator.validate(proposal.commands)
                validated_proposals.append(proposal)
            except SafetyViolation as e:
                logger.warning(
                    "Proposal %s failed safety validation: %s",
                    proposal.id,
                    e,
                )
                # Still include but mark as requiring manual review
                proposal.risks.append(
                    f"Safety validation warning: {e}. Manual review required."
                )
                validated_proposals.append(proposal)

        return validated_proposals

    def _create_investigation_proposal(
        self, rca: RootCauseAnalysis
    ) -> RemediationProposal:
        """Create a generic investigation proposal."""
        return RemediationProposal(
            id=uuid4(),
            incident_id=rca.incident_id,
            rca_id=rca.id,
            type=RemediationType.INVESTIGATION,
            title="Continue investigation",
            description=(
                "The RCA has insufficient evidence for a specific remediation. "
                "Continue investigation to gather more evidence."
            ),
            rationale=(
                f"Confidence: {rca.confidence:.2f} ({rca.confidence_band}). "
                "More evidence is needed."
            ),
            expected_effect="Gather additional evidence to improve RCA confidence",
            risks=[],
            prerequisites=[],
            commands=[],
            evidence_ids=rca.supporting_evidence_ids,
            requires_approval=True,
            status=RemediationStatus.PROPOSED,
        )
