from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID, uuid4

from backend.app.analysis.confidence import ConfidenceEngine
from backend.app.analysis.contradictions import Contradiction, ContradictionDetector
from backend.app.analysis.timeline import Timeline, TimelineEvent
from backend.app.llm.interface import LLMProvider, LLMProviderError
from backend.app.models.rca import (
    RootCauseAnalysis,
    RootCauseHypothesis,
    compute_confidence_band,
)

logger = logging.getLogger(__name__)

RCA_SYSTEM_PROMPT = """You are synthesizing an incident investigation.

Use ONLY the supplied evidence.

Do not invent facts.

Distinguish observed facts from inference.

Explicitly identify uncertainty.

Do not assign confidence.

Return structured JSON with these fields:
{
  "primary_hypothesis": {
    "title": "string",
    "explanation": "string",
    "contributing_factors": ["string"],
    "observed_facts": ["string"],
    "inferred_facts": ["string"],
    "uncertainties": ["string"]
  },
  "alternative_hypotheses": [
    {
      "title": "string",
      "explanation": "string",
      "contributing_factors": ["string"],
      "observed_facts": ["string"],
      "inferred_facts": ["string"],
      "uncertainties": ["string"]
    }
  ],
  "observed_facts": ["string"],
  "inferred_facts": ["string"],
  "uncertainties": ["string"]
}
"""


class RCASynthesisError(Exception):
    """Raised when RCA synthesis fails."""


class RCASynthesisEngine:
    """Deterministic RCA synthesis engine.

    Architecture:
    Verified Evidence → Deterministic Analysis → Structured Context →
    Qwen Synthesis → Pydantic Validation → Deterministic Confidence →
    Persisted RCA
    """

    def __init__(
        self,
        llm: LLMProvider,
        confidence_engine: ConfidenceEngine | None = None,
        contradiction_detector: ContradictionDetector | None = None,
    ) -> None:
        self._llm = llm
        self._confidence_engine = confidence_engine or ConfidenceEngine()
        self._contradiction_detector = contradiction_detector or ContradictionDetector()

    async def synthesize(
        self,
        *,
        incident_id: UUID,
        incident: dict[str, Any],
        findings: list[dict[str, Any]],
        evidence_items: list[dict[str, Any]],
        events: list[dict[str, Any]] | None = None,
    ) -> RootCauseAnalysis:
        """Synthesize an RCA from verified evidence.

        This method:
        1. Validates evidence references
        2. Builds timeline
        3. Detects contradictions
        4. Calculates deterministic confidence
        5. Calls LLM for synthesis
        6. Validates LLM output
        7. Returns structured RCA
        """
        # Step 1: Validate evidence references
        valid_findings, valid_evidence = self._validate_references(
            findings, evidence_items
        )

        # Step 2: Build timeline
        events = events or []
        timeline = Timeline.from_incident_data(
            incident, valid_evidence, valid_findings, events
        )

        # Step 3: Detect contradictions
        contradictions = self._contradiction_detector.analyze(
            valid_evidence, valid_findings
        )

        # Step 4: Calculate deterministic confidence
        confidence_score = self._confidence_engine.calculate(
            valid_findings, valid_evidence, contradictions, timeline
        )

        # Step 5: Call LLM for synthesis
        try:
            llm_result = await self._llm_synthesize(
                incident, valid_findings, valid_evidence, contradictions, timeline
            )
        except (LLMProviderError, RCASynthesisError) as e:
            logger.warning("LLM synthesis failed, using deterministic fallback: %s", e)
            llm_result = self._deterministic_fallback(
                valid_findings, valid_evidence, contradictions
            )

        # Step 6: Build hypotheses from LLM output
        primary = self._build_hypothesis(
            llm_result.get("primary_hypothesis", {}),
            valid_evidence,
            contradictions,
        )
        alternatives = [
            self._build_hypothesis(alt, valid_evidence, contradictions)
            for alt in llm_result.get("alternative_hypotheses", [])
        ]

        # Step 7: Build and return RCA
        band = compute_confidence_band(confidence_score.total)

        return RootCauseAnalysis(
            id=uuid4(),
            incident_id=incident_id,
            primary_hypothesis=primary,
            alternative_hypotheses=alternatives,
            confidence=confidence_score.total,
            confidence_band=band.value,
            supporting_evidence_ids=[e["id"] for e in valid_evidence],
            contradicting_evidence_ids=[
                c.evidence_a_id for c in contradictions
            ] + [c.evidence_b_id for c in contradictions],
            observed_facts=llm_result.get("observed_facts", []),
            inferred_facts=llm_result.get("inferred_facts", []),
            uncertainties=llm_result.get("uncertainties", []),
        )

    def _validate_references(
        self,
        findings: list[dict[str, Any]],
        evidence_items: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Validate that finding evidence references exist in evidence."""
        evidence_ids = {e["id"] for e in evidence_items}

        valid_findings = []
        for finding in findings:
            ref_ids = finding.get("evidence_ids", [])
            valid_refs = [eid for eid in ref_ids if eid in evidence_ids]
            if valid_refs:
                valid_findings.append(finding)

        valid_evidence = [
            e for e in evidence_items if e["id"] in evidence_ids
        ]

        return valid_findings, valid_evidence

    async def _llm_synthesize(
        self,
        incident: dict[str, Any],
        findings: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        contradictions: list[Contradiction],
        timeline: list[TimelineEvent],
    ) -> dict[str, Any]:
        """Call LLM for RCA synthesis."""
        # Build structured context
        context = self._build_llm_context(
            incident, findings, evidence, contradictions, timeline
        )

        user_prompt = (
            "Analyze the following incident and produce a root cause analysis.\n\n"
            f"Incident: {incident.get('title', 'Unknown')}\n"
            f"Severity: {incident.get('severity', 'Unknown')}\n"
            f"Service: {incident.get('service', 'Unknown')}\n"
            f"Description: {incident.get('description', '')}\n\n"
            f"Context:\n{context}\n\n"
            "Return ONLY valid JSON."
        )

        response = await self._llm.generate(
            user_prompt,
            system_prompt=RCA_SYSTEM_PROMPT,
        )

        return self._parse_llm_response(response)

    def _build_llm_context(
        self,
        incident: dict[str, Any],
        findings: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        contradictions: list[Contradiction],
        timeline: list[TimelineEvent],
    ) -> str:
        """Build structured context for LLM."""
        parts = []

        # Findings
        if findings:
            parts.append("FINDINGS:")
            for f in findings:
                parts.append(
                    f"- [{f.get('finding_type', 'unknown')}] "
                    f"{f.get('summary', 'No summary')} "
                    f"(confidence: {f.get('confidence', 0):.2f})"
                )

        # Evidence
        if evidence:
            parts.append("\nEVIDENCE:")
            for e in evidence:
                parts.append(
                    f"- [{e.get('source_type', 'unknown')}] "
                    f"{e.get('content', '')[:300]}"
                )

        # Contradictions
        if contradictions:
            parts.append("\nCONTRADICTIONS:")
            for c in contradictions:
                parts.append(f"- {c.description}")

        # Timeline
        if timeline:
            parts.append("\nTIMELINE:")
            for event in timeline[:20]:
                parts.append(
                    f"- {event.timestamp.isoformat()} "
                    f"[{event.event_type.value}] {event.description}"
                )

        return "\n".join(parts)

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        """Parse and validate LLM response."""
        text = response.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise RCASynthesisError(
                f"LLM returned invalid JSON: {e}"
            ) from e

        if not isinstance(data, dict):
            raise RCASynthesisError("LLM response is not a JSON object")

        # Validate required fields
        if "primary_hypothesis" not in data:
            raise RCASynthesisError("LLM response missing 'primary_hypothesis'")

        return data

    def _build_hypothesis(
        self,
        data: dict[str, Any],
        evidence: list[dict[str, Any]],
        contradictions: list[Contradiction],
    ) -> RootCauseHypothesis:
        """Build a RootCauseHypothesis from LLM output.

        The hypothesis confidence is derived from evidence, not from the LLM.
        """
        # Calculate hypothesis confidence based on evidence
        evidence_count = len(evidence)
        contradiction_count = len(contradictions)

        base_confidence = min(0.8, 0.3 + (evidence_count * 0.05))
        penalty = min(0.3, contradiction_count * 0.1)
        hypothesis_confidence = max(0.0, min(1.0, base_confidence - penalty))

        return RootCauseHypothesis(
            id=uuid4(),
            title=data.get("title", "Untitled hypothesis"),
            explanation=data.get("explanation", "No explanation provided"),
            confidence=hypothesis_confidence,
            supporting_evidence_ids=[e["id"] for e in evidence],
            contradicting_evidence_ids=[
                c.evidence_a_id for c in contradictions
            ],
            contributing_factors=data.get("contributing_factors", []),
        )

    def _deterministic_fallback(
        self,
        findings: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        contradictions: list[Contradiction],
    ) -> dict[str, Any]:
        """Produce a deterministic fallback when LLM fails."""
        observed = []
        inferred = []
        uncertainties = ["LLM synthesis failed - analysis is purely deterministic"]

        # Extract facts from findings
        for f in findings:
            summary = f.get("summary", "")
            if f.get("confidence", 0) > 0.5:
                observed.append(summary)
            else:
                inferred.append(summary)

        return {
            "primary_hypothesis": {
                "title": "Automated analysis based on available evidence",
                "explanation": (
                    "LLM synthesis failed. This hypothesis is based on "
                    "deterministic analysis of available evidence."
                ),
                "contributing_factors": [
                    f.get("summary", "") for f in findings[:5]
                ],
                "observed_facts": observed[:5],
                "inferred_facts": inferred[:5],
                "uncertainties": uncertainties,
            },
            "alternative_hypotheses": [],
            "observed_facts": observed[:10],
            "inferred_facts": inferred[:10],
            "uncertainties": uncertainties,
        }
