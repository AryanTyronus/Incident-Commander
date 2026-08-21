from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.analysis.contradictions import Contradiction


@dataclass
class ConfidenceWeights:
    """Configurable weights for confidence scoring."""

    support_weight: float = 0.30
    temporal_weight: float = 0.20
    correlation_weight: float = 0.20
    documentation_weight: float = 0.10
    contradiction_penalty: float = 0.15
    missing_data_penalty: float = 0.10


@dataclass
class ConfidenceScore:
    """Detailed confidence score breakdown."""

    total: float = 0.0
    support_score: float = 0.0
    temporal_score: float = 0.0
    correlation_score: float = 0.0
    documentation_score: float = 0.0
    contradiction_penalty: float = 0.0
    missing_data_penalty: float = 0.0
    factors: dict[str, Any] = field(default_factory=dict)


class ConfidenceEngine:
    """Deterministic confidence scoring engine.

    Calculates RCA confidence based on multiple factors:
    - Evidence support (how many findings support the hypothesis)
    - Temporal correlation (timeline alignment)
    - Stack trace / git correlation
    - Documentation / runbook agreement
    - Contradictory evidence penalty
    - Missing data penalty

    The LLM must NOT determine the final confidence.
    """

    def __init__(self, weights: ConfidenceWeights | None = None) -> None:
        self._weights = weights or ConfidenceWeights()

    def calculate(
        self,
        findings: list[dict[str, Any]],
        evidence_items: list[dict[str, Any]],
        contradictions: list[Contradiction],
        timeline_events: list[Any] | None = None,
    ) -> ConfidenceScore:
        """Calculate deterministic confidence score.

        Args:
            findings: Agent findings from Phase 3.
            evidence_items: Evidence items from Phase 3.
            contradictions: Detected contradictions.
            timeline_events: Timeline events (optional).

        Returns:
            ConfidenceScore with breakdown.
        """
        w = self._weights
        score = ConfidenceScore()

        # 1. Support score: based on number and quality of findings
        score.support_score = self._compute_support_score(findings, evidence_items)

        # 2. Temporal score: based on timeline coherence
        score.temporal_score = self._compute_temporal_score(
            findings, evidence_items, timeline_events
        )

        # 3. Correlation score: stack trace and git correlation
        score.correlation_score = self._compute_correlation_score(findings, evidence_items)

        # 4. Documentation score: runbook agreement
        score.documentation_score = self._compute_documentation_score(findings)

        # 5. Contradiction penalty
        score.contradiction_penalty = sum(c.impact_on_confidence for c in contradictions)

        # 6. Missing data penalty
        score.missing_data_penalty = self._compute_missing_data_penalty(findings, evidence_items)

        # Weighted sum
        raw = (
            score.support_score * w.support_weight
            + score.temporal_score * w.temporal_weight
            + score.correlation_score * w.correlation_weight
            + score.documentation_score * w.documentation_weight
            - score.contradiction_penalty * w.contradiction_penalty
            - score.missing_data_penalty * w.missing_data_penalty
        )

        # Normalize to 0.0-1.0
        score.total = max(0.0, min(1.0, raw))

        score.factors = {
            "support": score.support_score,
            "temporal": score.temporal_score,
            "correlation": score.correlation_score,
            "documentation": score.documentation_score,
            "contradiction_penalty": score.contradiction_penalty,
            "missing_data_penalty": score.missing_data_penalty,
            "weights": {
                "support": w.support_weight,
                "temporal": w.temporal_weight,
                "correlation": w.correlation_weight,
                "documentation": w.documentation_weight,
                "contradiction_penalty": w.contradiction_penalty,
                "missing_data_penalty": w.missing_data_penalty,
            },
        }

        return score

    def _compute_support_score(
        self,
        findings: list[dict[str, Any]],
        evidence_items: list[dict[str, Any]],
    ) -> float:
        """Score based on number and quality of findings."""
        if not findings:
            return 0.0

        # Count findings with evidence
        findings_with_evidence = sum(
            1 for f in findings if f.get("evidence_ids")
        )
        total_findings = len(findings)

        # Average finding confidence
        avg_confidence = (
            sum(f.get("confidence", 0) for f in findings) / total_findings
            if total_findings > 0
            else 0.0
        )

        # Evidence coverage
        evidence_count = len(evidence_items)
        evidence_score = min(1.0, evidence_count / 5.0)  # 5 pieces = full score

        return (
            (findings_with_evidence / max(total_findings, 1)) * 0.4
            + avg_confidence * 0.3
            + evidence_score * 0.3
        )

    def _compute_temporal_score(
        self,
        findings: list[dict[str, Any]],
        evidence_items: list[dict[str, Any]],
        timeline_events: list[Any] | None,
    ) -> float:
        """Score based on temporal coherence."""
        if not evidence_items:
            return 0.0

        # Check how many evidence items have timestamps
        timestamped = sum(
            1 for e in evidence_items if e.get("timestamp")
        )
        coverage = timestamped / max(len(evidence_items), 1)

        # If timeline events are provided, check ordering
        if timeline_events and len(timeline_events) > 1:
            ordered = all(
                timeline_events[i].timestamp <= timeline_events[i + 1].timestamp
                for i in range(len(timeline_events) - 1)
            )
            ordering_score = 1.0 if ordered else 0.5
        else:
            ordering_score = 0.5  # neutral if no timeline

        return coverage * 0.6 + ordering_score * 0.4

    def _compute_correlation_score(
        self,
        findings: list[dict[str, Any]],
        evidence_items: list[dict[str, Any]],
    ) -> float:
        """Score based on cross-source correlation."""
        source_types = {e.get("source_type") for e in evidence_items}

        has_log = "LOG" in source_types
        has_git = "GIT_COMMIT" in source_types or "GIT_DIFF" in source_types
        has_stack = "STACK_TRACE" in source_types
        has_runbook = "RUNBOOK" in source_types

        correlation_points = 0.0
        if has_log:
            correlation_points += 0.25
        if has_git:
            correlation_points += 0.25
        if has_stack:
            correlation_points += 0.25
        if has_runbook:
            correlation_points += 0.25

        # Bonus for cross-correlation
        if has_log and has_git:
            correlation_points += 0.1
        if has_stack and has_git:
            correlation_points += 0.1

        return min(1.0, correlation_points)

    def _compute_documentation_score(
        self, findings: list[dict[str, Any]]
    ) -> float:
        """Score based on runbook/documentation agreement."""
        runbook_findings = [
            f for f in findings
            if f.get("finding_type") == "RUNBOOK_MATCH"
        ]

        if not runbook_findings:
            return 0.0

        # Average confidence of runbook matches
        avg = sum(f.get("confidence", 0) for f in runbook_findings) / len(
            runbook_findings
        )
        return avg

    def _compute_missing_data_penalty(
        self,
        findings: list[dict[str, Any]],
        evidence_items: list[dict[str, Any]],
    ) -> float:
        """Penalize for missing data."""
        penalties = 0.0

        # No findings
        if not findings:
            penalties += 0.3

        # No evidence
        if not evidence_items:
            penalties += 0.3

        # Few evidence items
        if evidence_items and len(evidence_items) < 2:
            penalties += 0.1

        # No git evidence
        source_types = {e.get("source_type") for e in evidence_items}
        if "GIT_COMMIT" not in source_types and "GIT_DIFF" not in source_types:
            penalties += 0.1

        return min(1.0, penalties)
