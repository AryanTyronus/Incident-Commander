from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.app.analysis.rca import RCASynthesisEngine
from backend.app.approval.service import ApprovalService
from backend.app.models.rca import RootCauseAnalysis
from backend.app.models.remediation import RemediationProposal
from backend.app.remediation.planner import RemediationPlanner
from backend.app.repositories import (
    ApprovalRepository,
    EvidenceRepository,
    FindingRepository,
    IncidentRepository,
    RCARepository,
    RemediationRepository,
)

logger = logging.getLogger(__name__)


class RCAService:
    """Service for RCA synthesis and remediation planning.

    Responsibilities:
    - Load findings and evidence
    - Validate references
    - Build timeline
    - Detect contradictions
    - Calculate deterministic confidence
    - Call LLM for synthesis
    - Validate LLM output
    - Persist RCA
    - Generate remediation proposals
    - Create approval requests
    """

    def __init__(
        self,
        *,
        incident_repo: IncidentRepository,
        evidence_repo: EvidenceRepository,
        finding_repo: FindingRepository,
        rca_repo: RCARepository,
        remediation_repo: RemediationRepository,
        approval_repo: ApprovalRepository,
        rca_engine: RCASynthesisEngine,
        remediation_planner: RemediationPlanner,
        approval_service: ApprovalService,
    ) -> None:
        self._incident_repo = incident_repo
        self._evidence_repo = evidence_repo
        self._finding_repo = finding_repo
        self._rca_repo = rca_repo
        self._remediation_repo = remediation_repo
        self._approval_service = approval_service
        self._rca_engine = rca_engine
        self._remediation_planner = remediation_planner

    async def analyze_incident(
        self,
        incident_id: UUID,
    ) -> dict[str, Any]:
        """Perform full RCA analysis for an incident.

        Returns a dict with rca, remediation_proposals, and approvals.

        Analysis is idempotent. An incident carries at most one RCA
        (``rca_reports.incident_id`` is UNIQUE), so once one exists this returns
        the persisted analysis instead of synthesizing a second one. Repeating
        the synthesis would mint a fresh proposal set and strand the approval
        decisions an engineer has already recorded against the current one.
        """
        # Load incident
        incident = self._incident_repo.get_incident(incident_id)
        if incident is None:
            raise ValueError(f"Incident not found: {incident_id}")

        if self._rca_repo.get_by_incident_id(incident_id) is not None:
            logger.info(
                "Incident %s is already analyzed; returning the stored analysis",
                incident_id,
            )
            return self._stored_analysis(incident_id)

        # Load findings and evidence
        findings = self._finding_repo.list_for_incident(incident_id)
        evidence_items = self._evidence_repo.list_for_incident(incident_id)
        events = self._incident_repo._conn.execute(
            "SELECT * FROM incident_events WHERE incident_id = ? ORDER BY created_at",
            (str(incident_id),),
        ).fetchall()
        event_dicts = [
            {
                "id": UUID(row["id"]),
                "incident_id": UUID(row["incident_id"]),
                "event_type": row["event_type"],
                "created_at": datetime.fromisoformat(row["created_at"]),
                "payload": json.loads(row["payload"]) if row["payload"] else {},
            }
            for row in events
        ]

        # Synthesize RCA
        rca = await self._rca_engine.synthesize(
            incident_id=incident_id,
            incident=incident,
            findings=findings,
            evidence_items=evidence_items,
            events=event_dicts,
        )

        # Persist RCA. The guard above means no report exists for this incident
        # yet, so this is always an insert - and the proposals below can safely
        # reference ``rca.id`` through remediation_proposals.rca_id.
        now = datetime.now(UTC)
        self._rca_repo.create_rca(
            id=rca.id,
            incident_id=incident_id,
            report_json=rca.model_dump_json(),
            created_at=now,
            updated_at=now,
        )

        # Generate remediation proposals
        proposals = self._remediation_planner.generate_proposals(
            rca, evidence_items
        )

        # Persist proposals
        persisted_proposals = []
        for proposal in proposals:
            self._remediation_repo.create_proposal(
                id=proposal.id,
                incident_id=proposal.incident_id,
                rca_id=proposal.rca_id,
                type=proposal.type.value,
                title=proposal.title,
                description=proposal.description,
                rationale=proposal.rationale,
                expected_effect=proposal.expected_effect,
                risks=proposal.risks,
                prerequisites=proposal.prerequisites,
                commands=proposal.commands,
                patch_summary=proposal.patch_summary,
                evidence_ids=proposal.evidence_ids,
                requires_approval=proposal.requires_approval,
                status=proposal.status.value,
                created_at=proposal.created_at,
            )
            persisted_proposals.append(proposal)

        # Create approval requests
        approvals = []
        for proposal in persisted_proposals:
            if proposal.requires_approval:
                approval = self._approval_service.create_approval(
                    remediation_id=proposal.id,
                    incident_id=incident_id,
                )
                approvals.append(approval)

        return {
            "rca": rca,
            "remediation_proposals": persisted_proposals,
            "approvals": approvals,
        }

    def _stored_analysis(self, incident_id: UUID) -> dict[str, Any]:
        """Return the analysis already persisted for an incident.

        Same shape and types as a first-run ``analyze_incident``, carrying the
        proposals' and approvals' current state - so a repeated analyze shows
        any approve/reject decision already made rather than resetting it.
        """
        proposals = self.get_proposals(incident_id)
        approvals = []
        for proposal in proposals:
            approval = self._approval_service.get_by_remediation_id(proposal.id)
            if approval is not None:
                approvals.append(approval)

        return {
            "rca": self.get_rca(incident_id),
            "remediation_proposals": proposals,
            "approvals": approvals,
        }

    def get_rca(self, incident_id: UUID) -> RootCauseAnalysis | None:
        """Get the RCA for an incident."""
        record = self._rca_repo.get_by_incident_id(incident_id)
        if record is None:
            return None
        return RootCauseAnalysis.model_validate_json(record["report_json"])

    def get_proposals(self, incident_id: UUID) -> list[RemediationProposal]:
        """Get remediation proposals for an incident."""
        records = self._remediation_repo.list_for_incident(incident_id)
        return [
            RemediationProposal(
                id=r["id"],
                incident_id=r["incident_id"],
                rca_id=r["rca_id"],
                type=r["type"],
                title=r["title"],
                description=r["description"],
                rationale=r["rationale"],
                expected_effect=r["expected_effect"],
                risks=r["risks"],
                prerequisites=r["prerequisites"],
                commands=r["commands"],
                patch_summary=r["patch_summary"],
                evidence_ids=r["evidence_ids"],
                requires_approval=r["requires_approval"],
                status=r["status"],
                created_at=r["created_at"],
            )
            for r in records
        ]
