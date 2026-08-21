from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from backend.app.events.model import EventType, IncidentEvent

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publishes incident events to subscribers and persists to SQLite.

    Architecture:
    Domain event → SQLite audit event → EventPublisher → WebSocket subscribers
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._sequence_counters: dict[str, int] = defaultdict(int)

    def publish(
        self,
        *,
        incident_id: UUID,
        event_type: EventType,
        agent_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> IncidentEvent:
        """Publish an event and notify subscribers."""
        seq = self._next_sequence(str(incident_id))
        event = IncidentEvent(
            id=uuid4(),
            incident_id=incident_id,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            agent_name=agent_name,
            payload=payload or {},
            sequence=seq,
        )

        # Notify subscribers
        incident_key = str(incident_id)
        for callback in self._subscribers.get(incident_key, []):
            try:
                callback(event)
            except Exception as e:
                logger.error("Event subscriber callback failed: %s", e)

        logger.info(
            "Event published: incident=%s type=%s seq=%d agent=%s",
            incident_id,
            event_type.value,
            seq,
            agent_name or "none",
        )

        return event

    def subscribe(
        self, incident_id: UUID, callback: Callable[[IncidentEvent], None]
    ) -> None:
        """Subscribe to events for a specific incident."""
        key = str(incident_id)
        self._subscribers[key].append(callback)

    def unsubscribe(self, incident_id: UUID, callback: Callable) -> None:
        """Unsubscribe from events for a specific incident."""
        key = str(incident_id)
        if key in self._subscribers:
            self._subscribers[key] = [
                cb for cb in self._subscribers[key] if cb != callback
            ]

    def _next_sequence(self, incident_key: str) -> int:
        """Get next monotonically increasing sequence for an incident."""
        self._sequence_counters[incident_key] += 1
        return self._sequence_counters[incident_key]


# Global event publisher instance
event_publisher = EventPublisher()
