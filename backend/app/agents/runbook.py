from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.app.agents.base import InvestigationContext
from backend.app.models.agent_schemas import AgentResult
from backend.app.models.evidence import Evidence, SourceType
from backend.app.models.findings import AgentFinding, FindingType
from backend.app.repositories import EvidenceRepository, FindingRepository
from backend.app.tools.runbook_search import RunbookSearch


class RunbookAgent:
    """Runbook and documentation retrieval agent.

    Searches indexed runbooks and postmortems for relevant
    documentation. Does NOT hallucinate runbooks that don't exist.
    """

    name = "runbook"

    def __init__(
        self,
        evidence_repo: EvidenceRepository,
        finding_repo: FindingRepository,
        runbook_search: RunbookSearch | None = None,
    ) -> None:
        self._evidence_repo = evidence_repo
        self._finding_repo = finding_repo
        self._runbook_search = runbook_search

    async def run(self, context: InvestigationContext) -> AgentResult:
        """Search for relevant runbooks and documentation."""
        incident_id = context.incident_id

        # Build search query from incident context
        query = self._build_query(context)

        if not query:
            return AgentResult(
                agent_name=self.name,
                summary="Insufficient context to search for runbooks",
                confidence=0.0,
                metadata={"status": "no_query"},
            )

        if self._runbook_search is None:
            return AgentResult(
                agent_name=self.name,
                summary="Runbook search not configured",
                confidence=0.0,
                metadata={"status": "not_configured"},
            )

        try:
            results = self._runbook_search.search(query, top_k=5)
        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                summary=f"Runbook search failed: {e}",
                confidence=0.0,
                metadata={"status": "search_error", "error": str(e)},
            )

        # Create evidence for retrieved documents
        evidence_ids = []
        relevant_results = [r for r in results if r.similarity > 0.0]

        for result in relevant_results:
            evidence = self._create_runbook_evidence(incident_id, result)
            evidence_ids.append(evidence["id"])

        # Build finding
        finding = self._build_finding(
            incident_id, query, relevant_results, evidence_ids
        )

        return AgentResult(
            agent_name=self.name,
            summary=finding["summary"],
            findings=[{
                "finding_type": finding["finding_type"],
                "summary": finding["summary"],
                "confidence": finding["confidence"],
                "query": query,
                "results_count": len(relevant_results),
                "documents": [
                    {
                        "document_id": r.document_id,
                        "similarity": r.similarity,
                        "title": r.metadata.get("title", "Unknown"),
                        "type": r.metadata.get("document_type", "unknown"),
                        "excerpt": r.text[:200],
                    }
                    for r in relevant_results[:3]
                ],
            }],
            confidence=finding["confidence"],
            metadata={
                "evidence_ids": [str(eid) for eid in evidence_ids],
                "finding_id": str(finding["id"]),
                "query": query,
                "total_results": len(results),
                "relevant_results": len(relevant_results),
            },
        )

    def _build_query(self, context: InvestigationContext) -> str:
        """Build a search query from incident context."""
        parts = []

        # Use incident title/description
        incident = context.incident
        if incident.get("service"):
            parts.append(incident["service"])
        if incident.get("title"):
            parts.append(incident["title"])
        if incident.get("description"):
            # Take first 200 chars of description
            parts.append(incident["description"][:200])

        # Use error types from extra context
        error_type = context.extra.get("error_type")
        if error_type:
            parts.append(error_type)

        exception_type = context.extra.get("exception_type")
        if exception_type:
            parts.append(exception_type)

        return " ".join(parts) if parts else ""

    def _create_runbook_evidence(
        self, incident_id: Any, result: Any
    ) -> Evidence:
        """Create evidence from a runbook search result."""
        evidence = Evidence(
            id=uuid4(),
            incident_id=incident_id,
            source_type=SourceType.RUNBOOK,
            source_reference=result.metadata.get("document_path", "unknown"),
            content=result.text,
            metadata={
                "document_id": result.document_id,
                "chunk_id": result.chunk_id,
                "similarity": result.similarity,
                "title": result.metadata.get("title", ""),
                "document_type": result.metadata.get("document_type", ""),
            },
        )

        return self._evidence_repo.create_evidence(
            id=evidence.id,
            incident_id=evidence.incident_id,
            source_type=evidence.source_type.value,
            source_reference=evidence.source_reference,
            content=evidence.content,
            timestamp=evidence.timestamp,
            metadata=evidence.metadata,
            created_at=evidence.created_at,
        )

    def _build_finding(
        self,
        incident_id: Any,
        query: str,
        results: list[Any],
        evidence_ids: list[Any],
    ) -> AgentFinding:
        """Build a structured finding from runbook search."""
        if results:
            finding_type = FindingType.RUNBOOK_MATCH
            # Higher confidence when top result has high similarity
            top_similarity = results[0].similarity if results else 0.0
            confidence = min(0.85, 0.3 + top_similarity * 0.5)
        else:
            finding_type = FindingType.GENERAL
            confidence = 0.1

        # Build summary
        if results:
            doc_titles = [
                r.metadata.get("title", "Unknown") for r in results[:3]
            ]
            summary = (
                f"Found {len(results)} relevant document(s) for query '{query[:50]}': "
                + ", ".join(doc_titles)
            )
        else:
            summary = (
                f"No relevant runbooks found for query '{query[:50]}'. "
                "Consider creating documentation for this scenario."
            )

        finding = AgentFinding(
            id=uuid4(),
            incident_id=incident_id,
            agent_name=self.name,
            finding_type=finding_type,
            summary=summary,
            confidence=confidence,
            evidence_ids=evidence_ids,
            metadata={
                "query": query,
                "results_count": len(results),
            },
        )

        return self._finding_repo.create_finding(
            id=finding.id,
            incident_id=finding.incident_id,
            agent_name=finding.agent_name,
            finding_type=finding.finding_type.value,
            summary=finding.summary,
            confidence=finding.confidence,
            evidence_ids=finding.evidence_ids,
            created_at=finding.created_at,
            metadata=finding.metadata,
        )
