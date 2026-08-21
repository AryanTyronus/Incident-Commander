from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.app.analysis.timeline import EventType, Timeline, TimelineEvent


class TestTimeline:
    def test_empty_timeline(self) -> None:
        timeline = Timeline()
        events = timeline.build()
        assert len(events) == 0

    def test_sorted_events(self) -> None:
        timeline = Timeline()
        t1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC)
        timeline.add_event(TimelineEvent(timestamp=t1, event_type=EventType.CUSTOM))
        timeline.add_event(TimelineEvent(timestamp=t2, event_type=EventType.CUSTOM))
        events = timeline.build()
        assert events[0].timestamp == t2
        assert events[1].timestamp == t1

    def test_deterministic_sort(self) -> None:
        timeline = Timeline()
        t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        timeline.add_event(TimelineEvent(
            timestamp=t, event_type=EventType.CUSTOM, source="b"
        ))
        timeline.add_event(TimelineEvent(
            timestamp=t, event_type=EventType.CUSTOM, source="a"
        ))
        events = timeline.build()
        assert events[0].source == "a"
        assert events[1].source == "b"

    def test_from_incident_data(self) -> None:
        incident = {
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            "title": "Test incident",
            "severity": "SEV1",
            "service": "test-service",
        }
        evidence = [
            {
                "id": uuid4(),
                "source_type": "LOG",
                "timestamp": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                "created_at": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
                "metadata": {},
            },
        ]
        findings = []
        events = []
        timeline = Timeline.from_incident_data(incident, evidence, findings, events)
        assert len(timeline) == 2
