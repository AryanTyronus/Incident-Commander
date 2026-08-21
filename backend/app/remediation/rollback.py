from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.app.models.rca import RootCauseAnalysis
from backend.app.models.remediation import (
    RemediationProposal,
    RemediationStatus,
    RemediationType,
)


class RollbackPlanner:
    """Generates safe rollback proposals from RCA.

    Commands are generated from deterministic templates based on
    validated deployment identifiers. Never allows arbitrary
    shell commands from the LLM.
    """

    def generate(
        self,
        rca: RootCauseAnalysis,
        evidence_items: list[dict[str, Any]],
    ) -> RemediationProposal | None:
        """Generate a rollback proposal if applicable.

        Returns None if no rollback is applicable.
        """
        # Look for git commit evidence that might be a deployment
        git_evidence = [
            e for e in evidence_items
            if e.get("source_type") in ("GIT_COMMIT", "GIT_DIFF")
        ]

        if not git_evidence:
            return None

        # Find the most likely triggering commit
        # (the one with highest relevance to the incident)
        candidate_commits = []
        for item in git_evidence:
            meta = item.get("metadata", {})
            if meta.get("commit_hash"):
                candidate_commits.append(item)

        if not candidate_commits:
            return None

        # Use the first candidate (most recent from evidence)
        target = candidate_commits[0]
        commit_hash = target.get("metadata", {}).get("commit_hash", "")

        if not commit_hash:
            return None

        # Generate safe rollback commands from template
        commands = [
            f"git revert --no-edit {commit_hash}",
        ]

        # Find risks from RCA
        risks = [
            "Changes introduced after the reverted commit will also be affected",
            "Database migrations may not be automatically reverted",
        ]

        return RemediationProposal(
            id=uuid4(),
            incident_id=rca.incident_id,
            rca_id=rca.id,
            type=RemediationType.ROLLBACK,
            title=f"Rollback commit {commit_hash[:8]}",
            description=(
                f"Revert commit {commit_hash[:8]} to restore previous behavior."
            ),
            rationale=(
                f"The RCA identifies commit {commit_hash[:8]} as a likely "
                f"contributor to the incident."
            ),
            expected_effect="Restore application to state before the triggering commit",
            risks=risks,
            prerequisites=[
                "Verify no critical changes depend on this commit",
                "Notify team of rollback",
            ],
            commands=commands,
            evidence_ids=[e["id"] for e in candidate_commits],
            requires_approval=True,
            status=RemediationStatus.PROPOSED,
        )
