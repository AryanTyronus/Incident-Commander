from __future__ import annotations

import enum


class IncidentSource(enum.StrEnum):
    PAGERDUTY = "PAGERDUTY"
    SENTRY = "SENTRY"
    MANUAL = "MANUAL"
    RAW = "RAW"


class IncidentSeverity(enum.StrEnum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"


class IncidentStatus(enum.StrEnum):
    RECEIVED = "RECEIVED"
    TRIAGING = "TRIAGING"
    INVESTIGATING = "INVESTIGATING"
    SYNTHESIZING = "SYNTHESIZING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"
