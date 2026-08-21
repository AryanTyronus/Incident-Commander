from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class SourceType(enum.StrEnum):
    """Types of evidence sources."""

    LOG = "LOG"
    GIT_COMMIT = "GIT_COMMIT"
    GIT_DIFF = "GIT_DIFF"
    STACK_TRACE = "STACK_TRACE"
    RUNBOOK = "RUNBOOK"
    POSTMORTEM = "POSTMORTEM"


class Evidence(BaseModel):
    """A piece of forensic evidence with full provenance.

    Every evidence item must trace back to an actual source.
    Agents cannot fabricate evidence.
    """

    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    source_type: SourceType
    source_reference: str = Field(..., min_length=1)
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("source_reference")
    @classmethod
    def source_reference_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source_reference must not be blank")
        return v.strip()
