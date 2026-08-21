from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(enum.StrEnum):
    """Types of timeline events."""

    INCIDENT_CREATED = "INCIDENT_CREATED"
    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    LOG_ERROR = "LOG_ERROR"
    GIT_COMMIT = "GIT_COMMIT"
    DEPLOYMENT = "DEPLOYMENT"
    CUSTOM = "CUSTOM"


class TimelineEvent(BaseModel):
    """A single event in the incident timeline."""

    timestamp: datetime
    event_type: EventType
    source: str = Field(default="unknown")
    description: str = Field(default="")
    evidence_ids: list[UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Timeline:
    """Deterministic incident timeline builder.

    Collects events from multiple sources and sorts them
    deterministically by UTC timestamp.
    """

    def __init__(self) -> None:
        self._events: list[TimelineEvent] = []

    def add_event(self, event: TimelineEvent) -> None:
        """Add a single event to the timeline."""
        self._events.append(event)

    def add_events(self, events: list[TimelineEvent]) -> None:
        """Add multiple events to the timeline."""
        self._events.extend(events)

    def build(self) -> list[TimelineEvent]:
        """Build the sorted timeline.

        Events are sorted by timestamp, then by event_type
        for deterministic ordering of identical timestamps.
        """
        return sorted(
            self._events,
            key=lambda e: (e.timestamp, e.event_type.value, e.source),
        )

    @staticmethod
    def from_incident_data(
        incident: dict[str, Any],
        evidence_items: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> list[TimelineEvent]:
        """Build a timeline from incident data.

        This is a deterministic factory that constructs a timeline
        from persisted data without any LLM involvement.
        """
        timeline = Timeline()

        # Incident creation
        if incident.get("created_at"):
            timeline.add_event(TimelineEvent(
                timestamp=incident["created_at"],
                event_type=EventType.INCIDENT_CREATED,
                source="incident_service",
                description=f"Incident created: {incident.get('title', 'Unknown')}",
                metadata={
                    "severity": incident.get("severity", "unknown"),
                    "service": incident.get("service", "unknown"),
                },
            ))

        # Evidence items
        for item in evidence_items:
            timestamp = item.get("timestamp") or item.get("created_at")
            if timestamp:
                source_type = item.get("source_type", "unknown")
                timeline.add_event(TimelineEvent(
                    timestamp=timestamp,
                    event_type=EventType.EVIDENCE_COLLECTED,
                    source=source_type,
                    description=f"Evidence collected: {source_type}",
                    evidence_ids=[item["id"]],
                    metadata=item.get("metadata", {}),
                ))

        # Events
        for event in events:
            timestamp = event.get("created_at")
            if timestamp:
                timeline.add_event(TimelineEvent(
                    timestamp=timestamp,
                    event_type=EventType.CUSTOM,
                    source=event.get("event_type", "unknown"),
                    description=event.get("event_type", ""),
                    metadata=event.get("payload", {}),
                ))

        return timeline.build()
