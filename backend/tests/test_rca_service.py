from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from uuid import uuid4

from backend.app.analysis.rca import RCASynthesisEngine
from backend.app.llm.fake import FakeLLMProvider
from backend.app.repositories import (
    EvidenceRepository,
    FindingRepository,
)

VALID_RCA_JSON = """{
  "primary_hypothesis": {
    "title": "Deployment regression",
    "explanation": "Recent deployment changed validation behavior",
    "contributing_factors": ["New validation logic", "Missing rollback plan"],
    "observed_facts": ["Error rate increased at 14:32 UTC"],
    "inferred_facts": ["Commit abc123 is the likely cause"],
    "uncertainties": ["No direct reproduction performed"]
  },
  "alternative_hypotheses": [
    {
      "title": "Upstream payload change",
      "explanation": "Payload format from upstream service changed",
      "contributing_factors": ["API version mismatch"],
      "observed_facts": [],
      "inferred_facts": [],
      "uncertainties": ["No payload capture available"]
    }
  ],
  "observed_facts": ["Error rate increased", "Stack traces show validation error"],
  "inferred_facts": ["Deployment timing correlates with error onset"],
  "uncertainties": ["No direct reproduction"]
}"""

MALFORMED_JSON = "this is not json"
MISSING_FIELDS_JSON = '{"observed_facts": ["test"]}'


class TestRCASynthesisEngine:
    def setup_method(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.evidence_repo = EvidenceRepository(self._tmp.name)
        self.finding_repo = FindingRepository(self._tmp.name)

    async def test_synthesize_valid_response(self) -> None:
        llm = FakeLLMProvider(responses=[VALID_RCA_JSON])
        engine = RCASynthesisEngine(llm)

        incident_id = uuid4()
        incident = {
            "id": incident_id,
            "title": "Payment failures",
            "severity": "SEV1",
            "service": "payment-service",
            "description": "Users reporting payment failures",
            "created_at": datetime.now(UTC),
        }

        rca = await engine.synthesize(
            incident_id=incident_id,
            incident=incident,
            findings=[],
            evidence_items=[],
        )

        assert rca.incident_id == incident_id
        assert rca.primary_hypothesis.title == "Deployment regression"
        assert len(rca.alternative_hypotheses) == 1
        assert rca.confidence >= 0.0
        assert rca.confidence <= 1.0

    async def test_synthesize_malformed_json(self) -> None:
        llm = FakeLLMProvider(responses=[MALFORMED_JSON])
        engine = RCASynthesisEngine(llm)

        rca = await engine.synthesize(
            incident_id=uuid4(),
            incident={"title": "Test", "severity": "SEV2", "service": "test"},
            findings=[],
            evidence_items=[],
        )

        # Should fallback to deterministic analysis
        assert rca is not None
        assert "Automated analysis" in rca.primary_hypothesis.title

    async def test_synthesize_missing_fields(self) -> None:
        llm = FakeLLMProvider(responses=[MISSING_FIELDS_JSON])
        engine = RCASynthesisEngine(llm)

        rca = await engine.synthesize(
            incident_id=uuid4(),
            incident={"title": "Test", "severity": "SEV2", "service": "test"},
            findings=[],
            evidence_items=[],
        )

        # Should fallback to deterministic analysis
        assert rca is not None

    async def test_evidence_validation(self) -> None:
        llm = FakeLLMProvider(responses=[VALID_RCA_JSON])
        engine = RCASynthesisEngine(llm)

        real_evidence_id = uuid4()
        fake_evidence_id = uuid4()

        findings = [
            {
                "id": uuid4(),
                "evidence_ids": [real_evidence_id, fake_evidence_id],
                "confidence": 0.5,
                "finding_type": "GENERAL",
                "summary": "Test",
            }
        ]
        evidence_items = [
            {"id": real_evidence_id, "source_type": "LOG", "content": "Test"}
        ]

        rca = await engine.synthesize(
            incident_id=uuid4(),
            incident={"title": "Test", "severity": "SEV2", "service": "test"},
            findings=findings,
            evidence_items=evidence_items,
        )

        # Only real evidence should be referenced
        assert real_evidence_id in rca.supporting_evidence_ids
        assert fake_evidence_id not in rca.supporting_evidence_ids

    async def test_confidence_deterministic(self) -> None:
        llm = FakeLLMProvider(responses=[VALID_RCA_JSON])
        engine = RCASynthesisEngine(llm)

        rca = await engine.synthesize(
            incident_id=uuid4(),
            incident={"title": "Test", "severity": "SEV2", "service": "test"},
            findings=[],
            evidence_items=[],
        )

        # Confidence should be deterministic, not from LLM
        assert 0.0 <= rca.confidence <= 1.0
        assert rca.confidence_band in ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")

    async def test_llm_failure_preserves_analysis(self) -> None:
        from backend.app.llm.interface import LLMProviderError

        llm = FakeLLMProvider(error=LLMProviderError("LLM unavailable"))
        engine = RCASynthesisEngine(llm)

        rca = await engine.synthesize(
            incident_id=uuid4(),
            incident={"title": "Test", "severity": "SEV2", "service": "test"},
            findings=[],
            evidence_items=[],
        )

        assert rca is not None
        assert "Automated analysis" in rca.primary_hypothesis.title
        assert "LLM synthesis failed" in rca.uncertainties[0]
