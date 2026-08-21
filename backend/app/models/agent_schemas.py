from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class AgentRunStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvestigationStage(enum.StrEnum):
    NOT_STARTED = "NOT_STARTED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    AGGREGATING = "AGGREGATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class InvestigationTask(BaseModel):
    """A single task within an investigation plan."""

    id: UUID = Field(default_factory=uuid4)
    agent_name: str = Field(..., min_length=1, max_length=100)
    purpose: str = Field(..., min_length=1, max_length=500)
    priority: int = Field(default=1, ge=1, le=100)
    input: dict[str, Any] = Field(default_factory=dict)


class InvestigationPlan(BaseModel):
    """A structured plan for investigating an incident."""

    incident_id: UUID
    tasks: list[InvestigationTask] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentResult(BaseModel):
    """Result produced by an agent after execution."""

    agent_name: str
    summary: str = Field(default="")
    findings: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v


class AgentRun(BaseModel):
    """A record of a single agent execution."""

    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    agent_name: str
    status: AgentRunStatus = AgentRunStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InvestigationState(BaseModel):
    """Runtime state of an investigation."""

    incident_id: UUID
    status: InvestigationStage = InvestigationStage.NOT_STARTED
    active_runs: list[AgentRun] = Field(default_factory=list)
    completed_runs: list[AgentRun] = Field(default_factory=list)
    failed_runs: list[AgentRun] = Field(default_factory=list)
    findings: list[AgentResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    current_stage: InvestigationStage = InvestigationStage.NOT_STARTED


class InvestigationResponse(BaseModel):
    """API response for investigation start."""

    incident_id: UUID
    investigation_status: InvestigationStage
    message: str
