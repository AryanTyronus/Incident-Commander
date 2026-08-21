from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class RootCauseHypothesis(BaseModel):
    """A single root cause hypothesis."""

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., min_length=1, max_length=500)
    explanation: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    contradicting_evidence_ids: list[UUID] = Field(default_factory=list)
    contributing_factors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v


class RootCauseAnalysis(BaseModel):
    """Complete Root Cause Analysis for an incident."""

    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    primary_hypothesis: RootCauseHypothesis
    alternative_hypotheses: list[RootCauseHypothesis] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_band: str = Field(default="LOW")
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    contradicting_evidence_ids: list[UUID] = Field(default_factory=list)
    observed_facts: list[str] = Field(default_factory=list)
    inferred_facts: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v


class ConfidenceBand(enum.StrEnum):
    """Deterministic confidence interpretation bands."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


def compute_confidence_band(score: float) -> ConfidenceBand:
    """Compute confidence band from a numeric score."""
    if score < 0.40:
        return ConfidenceBand.LOW
    elif score < 0.70:
        return ConfidenceBand.MEDIUM
    elif score < 0.90:
        return ConfidenceBand.HIGH
    else:
        return ConfidenceBand.VERY_HIGH
