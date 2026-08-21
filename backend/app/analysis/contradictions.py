from __future__ import annotations

import enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ContradictionSeverity(enum.StrEnum):
    """Severity of a contradiction between evidence items."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Contradiction(BaseModel):
    """A contradiction between two pieces of evidence."""

    evidence_a_id: UUID
    evidence_b_id: UUID
    description: str
    severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
    impact_on_confidence: float = Field(default=0.1, ge=0.0, le=1.0)


class ContradictionDetector:
    """Deterministic contradiction detection engine.

    Analyzes evidence items and findings to identify conflicts
    that may affect confidence in the RCA.
    """

    def __init__(self) -> None:
        self._contradictions: list[Contradiction] = []

    def analyze(
        self,
        evidence_items: list[dict[str, Any]],
        findings: list[dict[str, Any]],
    ) -> list[Contradiction]:
        """Analyze evidence and findings for contradictions.

        This is a deterministic analysis that does not use the LLM.
        """
        self._contradictions = []

        # Check for temporal contradictions
        self._check_temporal_contradictions(evidence_items)

        # Check for git vs log contradictions
        self._check_git_log_contradictions(evidence_items, findings)

        # Check for finding confidence contradictions
        self._check_finding_contradictions(findings)

        return self._contradictions

    def _check_temporal_contradictions(
        self, evidence_items: list[dict[str, Any]]
    ) -> None:
        """Check for contradictions in timestamps."""
        timestamps_with_types: list[tuple[UUID, str, Any]] = []
        for item in evidence_items:
            ts = item.get("timestamp")
            if ts:
                timestamps_with_types.append(
                    (item["id"], item.get("source_type", ""), ts)
                )

        # Check for evidence claiming events before incident
        for i, (eid_a, type_a, ts_a) in enumerate(timestamps_with_types):
            for eid_b, type_b, ts_b in timestamps_with_types[i + 1:]:
                if type_a == type_b:
                    continue
                # Check if timestamps are significantly different
                if hasattr(ts_a, 'timestamp') and hasattr(ts_b, 'timestamp'):
                    diff = abs(ts_a.timestamp() - ts_b.timestamp())
                    if diff > 3600:  # More than 1 hour apart
                        self._contradictions.append(Contradiction(
                            evidence_a_id=eid_a,
                            evidence_b_id=eid_b,
                            description=(
                                f"Evidence timestamps differ significantly: "
                                f"{type_a} at {ts_a.isoformat()} vs "
                                f"{type_b} at {ts_b.isoformat()} "
                                f"({diff:.0f}s apart)"
                            ),
                            severity=ContradictionSeverity.LOW,
                            impact_on_confidence=0.05,
                        ))

    def _check_git_log_contradictions(
        self,
        evidence_items: list[dict[str, Any]],
        findings: list[dict[str, Any]],
    ) -> None:
        """Check for contradictions between git and log evidence."""
        git_evidence = [
            e for e in evidence_items if e.get("source_type") in ("GIT_COMMIT", "GIT_DIFF")
        ]
        log_evidence = [
            e for e in evidence_items if e.get("source_type") == "LOG"
        ]

        if not git_evidence or not log_evidence:
            return

        # Check if git commits are after log errors
        for git_item in git_evidence:
            git_ts = git_item.get("timestamp")
            if not git_ts:
                continue
            for log_item in log_evidence:
                log_ts = log_item.get("timestamp")
                if not log_ts:
                    continue
                if hasattr(git_ts, 'timestamp') and hasattr(log_ts, 'timestamp'):
                    if git_ts.timestamp() > log_ts.timestamp() + 300:
                        self._contradictions.append(Contradiction(
                            evidence_a_id=git_item["id"],
                            evidence_b_id=log_item["id"],
                            description=(
                                f"Git commit ({git_item.get('source_reference', '')}) "
                                f"occurred after log errors began. "
                                f"Commit at {git_ts.isoformat()}, "
                                f"errors at {log_ts.isoformat()}"
                            ),
                            severity=ContradictionSeverity.MEDIUM,
                            impact_on_confidence=0.15,
                        ))

    def _check_finding_contradictions(
        self, findings: list[dict[str, Any]]
    ) -> None:
        """Check for contradictions between findings."""
        if len(findings) < 2:
            return

        # Check for low confidence in one finding vs high in another
        for i, f_a in enumerate(findings):
            for f_b in findings[i + 1:]:
                conf_a = f_a.get("confidence", 0)
                conf_b = f_b.get("confidence", 0)
                # If one agent is very confident and another is not
                if conf_a > 0.7 and conf_b < 0.3:
                    self._contradictions.append(Contradiction(
                        evidence_a_id=UUID(int=0),
                        evidence_b_id=UUID(int=0),
                        description=(
                            f"Agent '{f_a.get('agent_name', 'unknown')}' has high "
                            f"confidence ({conf_a:.2f}) while "
                            f"'{f_b.get('agent_name', 'unknown')}' has low "
                            f"confidence ({conf_b:.2f})"
                        ),
                        severity=ContradictionSeverity.LOW,
                        impact_on_confidence=0.05,
                    ))

    @property
    def total_impact(self) -> float:
        """Calculate total confidence impact from all contradictions."""
        return min(0.5, sum(c.impact_on_confidence for c in self._contradictions))
