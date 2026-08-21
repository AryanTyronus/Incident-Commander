from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.app.models.rca import RootCauseAnalysis
from backend.app.models.remediation import (
    RemediationProposal,
    RemediationStatus,
    RemediationType,
)


class PatchPlanner:
    """Generates patch proposals from RCA.

    Phase 4 generates patch proposals, NOT actual filesystem
    modifications. The proposal can contain affected files,
    expected code change, reason, and tests that should be run.
    """

    def generate(
        self,
        rca: RootCauseAnalysis,
        evidence_items: list[dict[str, Any]],
    ) -> RemediationProposal | None:
        """Generate a patch proposal if applicable.

        Returns None if no patch is applicable.
        """
        # Look for git diff evidence
        diff_evidence = [
            e for e in evidence_items
            if e.get("source_type") == "GIT_DIFF"
        ]

        if not diff_evidence:
            return None

        # Extract affected files from diffs
        affected_files = set()
        for item in diff_evidence:
            meta = item.get("metadata", {})
            files = meta.get("files_changed", [])
            affected_files.update(files)

        if not affected_files:
            return None

        # Build patch summary
        files_list = sorted(affected_files)[:10]
        patch_summary = "Affected files:\n"
        for f in files_list:
            patch_summary += f"  - {f}\n"

        # Generate proposed changes description
        changes = []
        for item in diff_evidence:
            content = item.get("content", "")
            # Extract file names from content
            for line in content.split("\n"):
                if line.startswith("--- ") or line.startswith("+++ "):
                    fname = line.split(" ")[1] if " " in line else ""
                    if fname and fname != "/dev/null":
                        changes.append(fname)

        return RemediationProposal(
            id=uuid4(),
            incident_id=rca.incident_id,
            rca_id=rca.id,
            type=RemediationType.PATCH,
            title="Patch affected files",
            description=(
                f"Apply patches to {len(files_list)} file(s) to address "
                f"the root cause identified in the RCA."
            ),
            rationale=(
                "The RCA identifies code changes as a contributing factor. "
                "A patch should address the specific code issues."
            ),
            expected_effect=(
                "Fix the identified code issues while "
                "preserving existing functionality"
            ),
            risks=[
                "Patch may introduce new regressions",
                "Full test suite should be run before deployment",
            ],
            prerequisites=[
                "Review all affected files",
                "Run full test suite",
                "Verify patch addresses root cause",
            ],
            commands=[],  # No commands - this is a proposal only
            patch_summary=patch_summary,
            evidence_ids=[e["id"] for e in diff_evidence],
            requires_approval=True,
            status=RemediationStatus.PROPOSED,
        )
