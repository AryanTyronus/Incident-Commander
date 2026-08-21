from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from backend.app.models.enums import IncidentSeverity, IncidentSource, IncidentStatus


class IncidentCreate(BaseModel):
    """Request schema for creating an incident (manual/raw)."""

    model_config = {"extra": "forbid"}

    source: IncidentSource
    title: str = Field(..., min_length=1, max_length=500)
    severity: IncidentSeverity
    service: str = Field(..., min_length=1, max_length=200)
    environment: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=10000)
    stack_traces: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v.strip()

    @field_validator("service")
    @classmethod
    def service_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("service must not be blank")
        return v.strip()

    @field_validator("environment")
    @classmethod
    def environment_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("environment must not be blank")
        return v.strip()


class IncidentUpdateStatus(BaseModel):
    """Request schema for transitioning an incident's status."""

    status: IncidentStatus


class IncidentResponse(BaseModel):
    """Response schema for a single incident."""

    id: UUID
    source: IncidentSource
    title: str
    severity: IncidentSeverity
    service: str
    environment: str
    status: IncidentStatus
    description: str
    stack_traces: list[str]
    created_at: datetime
    updated_at: datetime
    raw_payload: dict[str, Any]

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    """Response schema for a list of incidents."""

    incidents: list[IncidentResponse]
    total: int
    limit: int
    offset: int


class WebhookResponse(BaseModel):
    """Response schema for webhook ingestion."""

    incident_id: UUID
    status: IncidentStatus
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
