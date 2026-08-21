from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ApprovalStatus(enum.StrEnum):
    """Status of an approval request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Approval(BaseModel):
    """A human approval record for a remediation proposal."""

    id: UUID = Field(default_factory=uuid4)
    remediation_id: UUID
    incident_id: UUID
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    approved_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None
