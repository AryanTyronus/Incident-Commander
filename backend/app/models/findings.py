from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class FindingType(enum.StrEnum):
    """Types of agent findings."""

    LOG_ANOMALY = "LOG_ANOMALY"
    CANDIDATE_CHANGE = "CANDIDATE_CHANGE"
    RUNBOOK_MATCH = "RUNBOOK_MATCH"
    ERROR_BURST = "ERROR_BURST"
    STACK_TRACE_MATCH = "STACK_TRACE_MATCH"
    GENERAL = "GENERAL"


class AgentFinding(BaseModel):
    """A structured finding produced by an investigation agent.

    Findings reference evidence by ID. Every finding must link to
    real evidence that has been persisted.
    """

    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    agent_name: str = Field(..., min_length=1, max_length=100)
    finding_type: FindingType
    summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v

    @field_validator("summary")
    @classmethod
    def summary_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("summary must not be blank")
        return v.strip()
