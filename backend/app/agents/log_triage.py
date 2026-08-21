from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.app.agents.base import InvestigationContext
from backend.app.models.agent_schemas import AgentResult
from backend.app.models.evidence import Evidence, SourceType
from backend.app.models.findings import AgentFinding, FindingType
from backend.app.repositories import EvidenceRepository, FindingRepository
from backend.app.tools.log_reader import LogAnalysis, LogReader


class LogTriageAgent:
    """Deterministic log analysis agent.

    Reads log files, counts errors/warnings, detects bursts,
    extracts stack traces, and produces structured findings.

    Qwen may summarize the output but must NOT fabricate log events.
    """

    name = "log_triage"

    def __init__(
        self,
        evidence_repo: EvidenceRepository,
        finding_repo: FindingRepository,
        log_reader: LogReader | None = None,
    ) -> None:
        self._evidence_repo = evidence_repo
        self._finding_repo = finding_repo
        self._log_reader = log_reader or LogReader()

    async def run(self, context: InvestigationContext) -> AgentResult:
        """Analyze logs for the given incident."""
        incident_id = context.incident_id
        log_path = context.extra.get("log_path")

        if not log_path:
            return AgentResult(
                agent_name=self.name,
                summary="No log file path provided in investigation context",
                confidence=0.0,
                metadata={"status": "no_input"},
            )

        try:
            analysis = self._log_reader.read_file(log_path)
        except FileNotFoundError:
            return AgentResult(
                agent_name=self.name,
                summary=f"Log file not found: {log_path}",
                confidence=0.0,
                metadata={"status": "file_not_found", "path": log_path},
            )
        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                summary=f"Failed to read log file: {e}",
                confidence=0.0,
                metadata={"status": "error", "error": str(e)},
            )

        # Create evidence items
        evidence_ids = []

        # Main log evidence
        log_evidence = self._create_log_evidence(incident_id, analysis, log_path)
        evidence_ids.append(log_evidence["id"])

        # Stack trace evidence (if any)
        for i, trace in enumerate(analysis.stack_traces[:5]):
            trace_evidence = self._create_stack_trace_evidence(
                incident_id, trace, log_path, i
            )
            evidence_ids.append(trace_evidence["id"])

        # Build finding
        finding = self._build_finding(incident_id, analysis, evidence_ids)

        return AgentResult(
            agent_name=self.name,
            summary=finding["summary"],
            findings=[{
                "finding_type": finding["finding_type"],
                "summary": finding["summary"],
                "confidence": finding["confidence"],
                "error_count": analysis.error_count,
                "warning_count": analysis.warning_count,
                "burst_windows": len(analysis.burst_windows),
                "stack_traces": len(analysis.stack_traces),
                "exception_counts": analysis.exception_counts,
            }],
            confidence=finding["confidence"],
            metadata={
                "evidence_ids": [str(eid) for eid in evidence_ids],
                "finding_id": str(finding["id"]),
                "log_path": log_path,
                "total_lines": analysis.total_lines,
                "error_count": analysis.error_count,
                "warning_count": analysis.warning_count,
            },
        )

    def _create_log_evidence(
        self,
        incident_id: Any,
        analysis: LogAnalysis,
        log_path: str,
    ) -> Evidence:
        """Create evidence from log analysis."""
        # Build summary content
        content_parts = [
            f"Log file: {log_path}",
            f"Total lines: {analysis.total_lines}",
            f"Errors: {analysis.error_count}",
            f"Warnings: {analysis.warning_count}",
        ]

        if analysis.first_timestamp:
            content_parts.append(
                f"Time range: {analysis.first_timestamp.isoformat()} to "
                f"{analysis.last_timestamp.isoformat() if analysis.last_timestamp else 'N/A'}"
            )

        if analysis.exception_counts:
            content_parts.append("Exceptions:")
            for exc, count in analysis.exception_counts.items():
                content_parts.append(f"  {exc}: {count}")

        if analysis.burst_windows:
            content_parts.append(f"Error bursts: {len(analysis.burst_windows)}")
            for burst in analysis.burst_windows:
                content_parts.append(
                    f"  {burst.error_count} errors in "
                    f"{burst.window_seconds:.0f}s window"
                )

        # Include representative errors
        if analysis.representative_errors:
            content_parts.append("Representative errors:")
            for line in analysis.representative_errors[:5]:
                content_parts.append(f"  Line {line.line_number}: {line.raw[:200]}")

        content = "\n".join(content_parts)

        evidence = Evidence(
            id=uuid4(),
            incident_id=incident_id,
            source_type=SourceType.LOG,
            source_reference=log_path,
            content=content,
            timestamp=analysis.last_timestamp,
            metadata={
                "total_lines": analysis.total_lines,
                "error_count": analysis.error_count,
                "warning_count": analysis.warning_count,
                "exception_counts": analysis.exception_counts,
                "burst_count": len(analysis.burst_windows),
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

    def _create_stack_trace_evidence(
        self,
        incident_id: Any,
        trace: str,
        log_path: str,
        index: int,
    ) -> Evidence:
        """Create evidence from a stack trace."""
        evidence = Evidence(
            id=uuid4(),
            incident_id=incident_id,
            source_type=SourceType.STACK_TRACE,
            source_reference=f"{log_path}:stack_trace_{index}",
            content=trace,
            metadata={"trace_index": index},
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
        analysis: LogAnalysis,
        evidence_ids: list[Any],
    ) -> AgentFinding:
        """Build a structured finding from log analysis."""
        # Determine finding type and confidence
        has_bursts = len(analysis.burst_windows) > 0
        has_errors = analysis.error_count > 0
        has_traces = len(analysis.stack_traces) > 0

        if has_bursts:
            finding_type = FindingType.ERROR_BURST
            confidence = min(0.9, 0.5 + (analysis.error_count / 100))
        elif has_errors and has_traces:
            finding_type = FindingType.LOG_ANOMALY
            confidence = min(0.85, 0.4 + (analysis.error_count / 50))
        elif has_errors:
            finding_type = FindingType.LOG_ANOMALY
            confidence = min(0.7, 0.3 + (analysis.error_count / 100))
        else:
            finding_type = FindingType.GENERAL
            confidence = 0.2

        # Build summary
        summary_parts = []
        if analysis.error_count > 0:
            summary_parts.append(f"{analysis.error_count} errors detected")
        if analysis.warning_count > 0:
            summary_parts.append(f"{analysis.warning_count} warnings")
        if analysis.burst_windows:
            summary_parts.append(
                f"{len(analysis.burst_windows)} error burst(s) detected"
            )
        if analysis.stack_traces:
            summary_parts.append(
                f"{len(analysis.stack_traces)} stack trace(s) found"
            )
        if analysis.exception_counts:
            top_exceptions = sorted(
                analysis.exception_counts.items(), key=lambda x: x[1], reverse=True
            )[:3]
            exc_summary = ", ".join(
                f"{exc}({count})" for exc, count in top_exceptions
            )
            summary_parts.append(f"Top exceptions: {exc_summary}")

        summary = (
            "; ".join(summary_parts) if summary_parts else "No significant log anomalies"
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
                "error_count": analysis.error_count,
                "warning_count": analysis.warning_count,
                "burst_windows": len(analysis.burst_windows),
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
