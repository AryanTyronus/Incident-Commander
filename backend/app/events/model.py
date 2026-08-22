from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(enum.StrEnum):
    """Stable event types for incident lifecycle."""

    INCIDENT_CREATED = "INCIDENT_CREATED"
    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    INVESTIGATION_STAGE_CHANGED = "INVESTIGATION_STAGE_CHANGED"
    PLAN_CREATED = "PLAN_CREATED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_PROGRESS = "AGENT_PROGRESS"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    FINDING_CREATED = "FINDING_CREATED"
    RCA_STARTED = "RCA_STARTED"
    RCA_COMPLETED = "RCA_COMPLETED"
    REMEDIATION_PROPOSED = "REMEDIATION_PROPOSED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    REMEDIATION_APPROVED = "REMEDIATION_APPROVED"
    REMEDIATION_REJECTED = "REMEDIATION_REJECTED"
    INVESTIGATION_COMPLETED = "INVESTIGATION_COMPLETED"
    INVESTIGATION_FAILED = "INVESTIGATION_FAILED"


class IncidentEvent(BaseModel):
    """A structured event for incident lifecycle."""

    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    sequence: int = 0
