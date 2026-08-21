from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class RemediationType(enum.StrEnum):
    """Types of remediation proposals."""

    ROLLBACK = "ROLLBACK"
    PATCH = "PATCH"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    INVESTIGATION = "INVESTIGATION"


class RemediationStatus(enum.StrEnum):
    """Status of a remediation proposal."""

    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class RemediationProposal(BaseModel):
    """A remediation proposal generated from the RCA."""

    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    rca_id: UUID
    type: RemediationType
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    rationale: str = Field(default="")
    expected_effect: str = Field(default="")
    risks: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    patch_summary: str = Field(default="")
    evidence_ids: list[UUID] = Field(default_factory=list)
    requires_approval: bool = Field(default=True)
    status: RemediationStatus = Field(default=RemediationStatus.PROPOSED)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("commands")
    @classmethod
    def validate_commands(cls, v: list[str]) -> list[str]:
        for cmd in v:
            if not cmd.strip():
                raise ValueError("commands must not contain empty strings")
        return v
