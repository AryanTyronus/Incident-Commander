from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from backend.app.dependencies import (
    ApprovalServiceDep,
    EvidenceRepoDep,
    FindingRepoDep,
    InvestigationRepoDep,
    InvestigationRunnerDep,
    RCAServiceDep,
    RemediationRepoDep,
    ServiceDep,
)
from backend.app.models.agent_schemas import InvestigationResponse, InvestigationStage
from backend.app.models.schemas import (
    ErrorResponse,
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
    IncidentUpdateStatus,
)
from backend.app.services.incident_service import (
    IncidentNotFoundError,
    InvalidTransitionError,
)
from backend.app.services.investigation_runner import ACTIVE_STAGES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

# Approval decisions address a remediation proposal by its own id, not through
# an incident, so they live on their own prefix. Declaring them on `router`
# would nest them under /api/incidents, which is not the path clients call.
remediation_router = APIRouter(prefix="/api/remediations", tags=["remediation"])


@router.post("", response_model=IncidentResponse, status_code=201)
async def create_incident(
    body: IncidentCreate,
    svc: ServiceDep,
) -> dict:
    incident = svc.create_incident(
        source=body.source,
        title=body.title,
        severity=body.severity,
        service=body.service,
        environment=body.environment,
        description=body.description,
        stack_traces=body.stack_traces,
        raw_payload=body.raw_payload,
    )
    return incident


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    svc: ServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    incidents, total = svc.list_incidents(limit=limit, offset=offset)
    return {
        "incidents": incidents,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_incident(
    incident_id: UUID,
    svc: ServiceDep,
) -> dict:
    try:
        return svc.get_incident(incident_id)
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")


@router.patch(
    "/{incident_id}/status",
    response_model=IncidentResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def update_incident_status(
    incident_id: UUID,
    body: IncidentUpdateStatus,
    svc: ServiceDep,
) -> dict:
    try:
        return svc.transition_status(incident_id, body.status)
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post(
    "/{incident_id}/investigate",
    response_model=InvestigationResponse,
    status_code=202,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def start_investigation(
    incident_id: UUID,
    background_tasks: BackgroundTasks,
    svc: ServiceDep,
    investigation_repo: InvestigationRepoDep,
    runner: InvestigationRunnerDep,
) -> dict:
    """Accept an investigation request and run it in the background.

    An investigation is minutes of LLM planning and agent work, so the request
    only validates and schedules it, then answers 202. Progress and the terminal
    outcome are streamed over ``/api/incidents/{incident_id}/stream``; poll
    ``GET /api/incidents/{incident_id}/investigation`` for the persisted state.
    """
    try:
        svc.get_incident(incident_id)
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail="Incident not found")

    existing = investigation_repo.get_by_incident_id(incident_id)
    if existing is not None and existing["stage"] in ACTIVE_STAGES:
        raise HTTPException(
            status_code=409,
            detail=f"Investigation already running for {incident_id}",
        )

    background_tasks.add_task(runner.run, incident_id)

    return {
        "incident_id": str(incident_id),
        "investigation_status": InvestigationStage.PLANNING.value,
        "message": "Investigation accepted and running in the background",
    }


@router.get(
    "/{incident_id}/investigation",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_investigation(
    incident_id: UUID,
    investigation_repo: InvestigationRepoDep,
) -> dict:
    """Get the investigation state for an incident."""
    from backend.app.models.agent_schemas import InvestigationState

    record = investigation_repo.get_by_incident_id(incident_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    state = InvestigationState.model_validate_json(record["state_json"])
    return {
        "incident_id": str(incident_id),
        "investigation_id": str(record["id"]),
        "stage": record["stage"],
        "state": state.model_dump(mode="json"),
        "created_at": record["created_at"].isoformat(),
        "updated_at": record["updated_at"].isoformat(),
    }


@router.get(
    "/{incident_id}/findings",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_findings(
    incident_id: UUID,
    finding_repo: FindingRepoDep,
) -> dict:
    """Get all findings for an incident."""
    findings = finding_repo.list_for_incident(incident_id)
    return {
        "incident_id": str(incident_id),
        "findings": [
            {
                "id": str(f["id"]),
                "agent_name": f["agent_name"],
                "finding_type": f["finding_type"],
                "summary": f["summary"],
                "confidence": f["confidence"],
                "evidence_ids": [str(eid) for eid in f["evidence_ids"]],
                "created_at": f["created_at"].isoformat(),
                "metadata": f["metadata"],
            }
            for f in findings
        ],
        "total": len(findings),
    }


@router.get(
    "/{incident_id}/evidence",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_evidence(
    incident_id: UUID,
    evidence_repo: EvidenceRepoDep,
) -> dict:
    """Get all evidence for an incident."""
    evidence = evidence_repo.list_for_incident(incident_id)
    return {
        "incident_id": str(incident_id),
        "evidence": [
            {
                "id": str(e["id"]),
                "source_type": e["source_type"],
                "source_reference": e["source_reference"],
                "content": e["content"],
                "timestamp": e["timestamp"].isoformat() if e["timestamp"] else None,
                "metadata": e["metadata"],
                "created_at": e["created_at"].isoformat(),
            }
            for e in evidence
        ],
        "total": len(evidence),
    }


# ------------------------------------------------------------------
# Phase 4: RCA, Remediation, and Approval endpoints
# ------------------------------------------------------------------

@router.post(
    "/{incident_id}/analyze",
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def analyze_incident(
    incident_id: UUID,
    rca_service: RCAServiceDep,
) -> dict:
    """Perform RCA analysis and generate remediation proposals."""

    try:
        result = await rca_service.analyze_incident(incident_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # The catch-all keeps the JSON error contract, but log the traceback:
        # a bare "Analysis failed: <msg>" is not enough to diagnose from.
        logger.exception("Analysis failed for incident %s", incident_id)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    rca = result["rca"]
    proposals = result["remediation_proposals"]
    approvals = result["approvals"]

    return {
        "incident_id": str(incident_id),
        "rca": {
            "id": str(rca.id),
            "incident_id": str(rca.incident_id),
            "primary_hypothesis": {
                "id": str(rca.primary_hypothesis.id),
                "title": rca.primary_hypothesis.title,
                "explanation": rca.primary_hypothesis.explanation,
                "confidence": rca.primary_hypothesis.confidence,
            },
            "confidence": rca.confidence,
            "confidence_band": rca.confidence_band,
            "observed_facts": rca.observed_facts,
            "inferred_facts": rca.inferred_facts,
            "uncertainties": rca.uncertainties,
            "created_at": rca.created_at.isoformat(),
        },
        "remediation_proposals": [
            {
                "id": str(p.id),
                "type": p.type.value,
                "title": p.title,
                "description": p.description,
                "status": p.status.value,
                "requires_approval": p.requires_approval,
                "commands": p.commands,
                "created_at": p.created_at.isoformat(),
            }
            for p in proposals
        ],
        "approvals": [
            {
                "id": str(a.id),
                "status": a.status.value,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ],
    }


@router.get(
    "/{incident_id}/rca",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_rca(
    incident_id: UUID,
    rca_service: RCAServiceDep,
) -> dict:
    """Get the RCA for an incident."""
    rca = rca_service.get_rca(incident_id)
    if rca is None:
        raise HTTPException(status_code=404, detail="RCA not found")

    return {
        "incident_id": str(incident_id),
        "rca": {
            "id": str(rca.id),
            "incident_id": str(rca.incident_id),
            "primary_hypothesis": {
                "id": str(rca.primary_hypothesis.id),
                "title": rca.primary_hypothesis.title,
                "explanation": rca.primary_hypothesis.explanation,
                "confidence": rca.primary_hypothesis.confidence,
            },
            "alternative_hypotheses": [
                {
                    "id": str(h.id),
                    "title": h.title,
                    "explanation": h.explanation,
                    "confidence": h.confidence,
                }
                for h in rca.alternative_hypotheses
            ],
            "confidence": rca.confidence,
            "confidence_band": rca.confidence_band,
            "observed_facts": rca.observed_facts,
            "inferred_facts": rca.inferred_facts,
            "uncertainties": rca.uncertainties,
            "created_at": rca.created_at.isoformat(),
        },
    }


@router.get(
    "/{incident_id}/remediation",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_remediation(
    incident_id: UUID,
    rca_service: RCAServiceDep,
) -> dict:
    """Get remediation proposals for an incident."""
    proposals = rca_service.get_proposals(incident_id)

    return {
        "incident_id": str(incident_id),
        "proposals": [
            {
                "id": str(p.id),
                "type": p.type.value,
                "title": p.title,
                "description": p.description,
                "rationale": p.rationale,
                "expected_effect": p.expected_effect,
                "risks": p.risks,
                "prerequisites": p.prerequisites,
                "commands": p.commands,
                "patch_summary": p.patch_summary,
                "status": p.status.value,
                "requires_approval": p.requires_approval,
                "created_at": p.created_at.isoformat(),
            }
            for p in proposals
        ],
        "total": len(proposals),
    }


@remediation_router.post(
    "/{remediation_id}/approve",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def approve_remediation(
    remediation_id: UUID,
    approval_service: ApprovalServiceDep,
    remediation_repo: RemediationRepoDep,
    approved_by: str = "engineer",
) -> dict:
    """Approve a remediation proposal."""
    from backend.app.approval.service import (
        DuplicateDecisionError,
    )

    try:
        approval = approval_service.get_by_remediation_id(remediation_id)
        if approval is None:
            raise HTTPException(status_code=404, detail="Approval not found")

        approved = approval_service.approve(
            approval.id,
            approved_by=approved_by,
        )

        # Update remediation status
        remediation_repo.update_status(
            proposal_id=remediation_id,
            status="APPROVED",
        )

        return {
            "approval_id": str(approved.id),
            "remediation_id": str(remediation_id),
            "status": approved.status.value,
            "approved_by": approved.approved_by,
            "decided_at": approved.decided_at.isoformat() if approved.decided_at else None,
            "message": "Remediation approved. NOTE: No execution has occurred.",
        }
    except DuplicateDecisionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@remediation_router.post(
    "/{remediation_id}/reject",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def reject_remediation(
    remediation_id: UUID,
    approval_service: ApprovalServiceDep,
    remediation_repo: RemediationRepoDep,
    rejected_by: str = "engineer",
) -> dict:
    """Reject a remediation proposal."""
    from backend.app.approval.service import (
        DuplicateDecisionError,
    )

    try:
        approval = approval_service.get_by_remediation_id(remediation_id)
        if approval is None:
            raise HTTPException(status_code=404, detail="Approval not found")

        rejected = approval_service.reject(
            approval.id,
            rejected_by=rejected_by,
        )

        # Update remediation status
        remediation_repo.update_status(
            proposal_id=remediation_id,
            status="REJECTED",
        )

        return {
            "approval_id": str(rejected.id),
            "remediation_id": str(remediation_id),
            "status": rejected.status.value,
            "approved_by": rejected.approved_by,
            "decided_at": rejected.decided_at.isoformat() if rejected.decided_at else None,
            "message": "Remediation rejected.",
        }
    except DuplicateDecisionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get(
    "/{incident_id}/events",
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_events(
    incident_id: UUID,
    evidence_repo: EvidenceRepoDep,
) -> dict:
    """Get all events for an incident ordered by sequence."""
    import json

    from backend.app.config import settings as cfg
    from backend.app.db import get_connection

    conn = get_connection(cfg.DATABASE_PATH)
    try:
        rows = conn.execute(
            "SELECT * FROM incident_events WHERE incident_id = ? ORDER BY created_at",
            (str(incident_id),),
        ).fetchall()
    finally:
        conn.close()

    events = []
    for i, row in enumerate(rows):
        payload = json.loads(row["payload"]) if row["payload"] else {}
        events.append({
            "id": row["id"],
            "incident_id": row["incident_id"],
            "event_type": row["event_type"],
            "source": row["source"],
            "payload": payload,
            "created_at": row["created_at"],
            "sequence": i + 1,
        })

    return {
        "incident_id": str(incident_id),
        "events": events,
        "total": len(events),
    }
