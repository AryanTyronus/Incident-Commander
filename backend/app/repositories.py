from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.app.db import get_connection, initialize_database


class IncidentRepository:
    """Data access layer for incidents and events."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = get_connection(db_path)
        initialize_database(self._conn)

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Incidents
    # ------------------------------------------------------------------

    def create_incident(
        self,
        *,
        id: UUID,
        source: str,
        title: str,
        severity: str,
        service: str,
        environment: str,
        status: str,
        description: str,
        stack_traces: list[str],
        created_at: datetime,
        updated_at: datetime,
        raw_payload: dict[str, Any],
    ) -> dict[str, Any]:
        now_iso = datetime.now(UTC).isoformat()
        created_iso = created_at.isoformat() if created_at else now_iso
        updated_iso = updated_at.isoformat() if updated_at else now_iso

        self._conn.execute(
            """
            INSERT INTO incidents
                (id, source, title, severity, service, environment,
                 status, description, stack_traces, created_at, updated_at, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(id),
                source,
                title,
                severity,
                service,
                environment,
                status,
                description,
                json.dumps(stack_traces),
                created_iso,
                updated_iso,
                json.dumps(raw_payload),
            ),
        )
        self._conn.commit()
        return self.get_incident(id)  # type: ignore[return-value]

    def get_incident(self, incident_id: UUID) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM incidents WHERE id = ?", (str(incident_id),)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_incidents(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_incidents(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM incidents").fetchone()
        return row["cnt"] if row else 0

    def update_incident_status(
        self,
        incident_id: UUID,
        new_status: str,
    ) -> dict[str, Any]:
        now_iso = datetime.now(UTC).isoformat()
        self._conn.execute(
            "UPDATE incidents SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now_iso, str(incident_id)),
        )
        self._conn.commit()
        return self.get_incident(incident_id)  # type: ignore[return-value]

    def find_incident_by_external_event(
        self, source: str, external_event_id: str
    ) -> dict[str, Any] | None:
        """Find an incident that was created from a specific external event."""
        row = self._conn.execute(
            """
            SELECT i.* FROM incidents i
            JOIN incident_events e ON e.incident_id = i.id
            WHERE e.source = ? AND e.external_event_id = ?
            LIMIT 1
            """,
            (source, external_event_id),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def record_event(
        self,
        *,
        id: UUID,
        incident_id: UUID,
        event_type: str,
        source: str | None = None,
        external_event_id: str | None = None,
        old_status: str | None,
        new_status: str | None,
        payload: dict[str, Any],
        created_at: datetime,
    ) -> dict[str, Any]:
        now_iso = datetime.now(UTC).isoformat()
        created_iso = created_at.isoformat() if created_at else now_iso

        self._conn.execute(
            """
            INSERT INTO incident_events
                (id, incident_id, event_type, source, external_event_id,
                 old_status, new_status, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(id),
                str(incident_id),
                event_type,
                source,
                external_event_id,
                old_status,
                new_status,
                json.dumps(payload),
                created_iso,
            ),
        )
        self._conn.commit()
        return {
            "id": id,
            "incident_id": incident_id,
            "event_type": event_type,
            "source": source,
            "external_event_id": external_event_id,
            "old_status": old_status,
            "new_status": new_status,
            "payload": payload,
            "created_at": created_at,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["id"] = UUID(d["id"])
        d["stack_traces"] = json.loads(d["stack_traces"])
        d["raw_payload"] = json.loads(d["raw_payload"])
        d["created_at"] = datetime.fromisoformat(d["created_at"])
        d["updated_at"] = datetime.fromisoformat(d["updated_at"])
        return d


class AgentRunRepository:
    """Data access layer for agent runs."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = get_connection(db_path)
        initialize_database(self._conn)

    def close(self) -> None:
        self._conn.close()

    def create_run(self, run: Any) -> Any:
        """Create a new agent run record."""

        datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            INSERT INTO agent_runs
                (id, incident_id, agent_name, status, started_at,
                 completed_at, input_json, output_json, error, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(run.id),
                str(run.incident_id),
                run.agent_name,
                run.status.value,
                run.started_at.isoformat() if run.started_at else None,
                run.completed_at.isoformat() if run.completed_at else None,
                json.dumps(run.input),
                json.dumps(run.output) if run.output else None,
                run.error,
                json.dumps(run.metadata),
            ),
        )
        self._conn.commit()
        return self.get_run(run.id)  # type: ignore[return-value]

    def get_run(self, run_id: UUID) -> Any | None:
        """Get an agent run by ID."""

        row = self._conn.execute(
            "SELECT * FROM agent_runs WHERE id = ?", (str(run_id),)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def get_runs_for_incident(self, incident_id: UUID) -> list[Any]:
        """Get all agent runs for an incident."""
        rows = self._conn.execute(
            "SELECT * FROM agent_runs WHERE incident_id = ? ORDER BY started_at",
            (str(incident_id),),
        ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def update_run(self, run: Any) -> Any:
        """Update an existing agent run."""
        self._conn.execute(
            """
            UPDATE agent_runs
            SET status = ?, started_at = ?, completed_at = ?,
                output_json = ?, error = ?, metadata_json = ?
            WHERE id = ?
            """,
            (
                run.status.value,
                run.started_at.isoformat() if run.started_at else None,
                run.completed_at.isoformat() if run.completed_at else None,
                json.dumps(run.output) if run.output else None,
                run.error,
                json.dumps(run.metadata),
                str(run.id),
            ),
        )
        self._conn.commit()
        return self.get_run(run.id)  # type: ignore[return-value]

    def _row_to_run(self, row: sqlite3.Row) -> Any:
        """Convert a database row to an AgentRun."""
        from backend.app.models.agent_schemas import AgentRun, AgentRunStatus

        return AgentRun(
            id=UUID(row["id"]),
            incident_id=UUID(row["incident_id"]),
            agent_name=row["agent_name"],
            status=AgentRunStatus(row["status"]),
            started_at=(
                datetime.fromisoformat(row["started_at"])
                if row["started_at"]
                else None
            ),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
            input=json.loads(row["input_json"]),
            output=json.loads(row["output_json"]) if row["output_json"] else None,
            error=row["error"],
            metadata=json.loads(row["metadata_json"]),
        )


class InvestigationRepository:
    """Data access layer for investigation state persistence."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = get_connection(db_path)
        initialize_database(self._conn)

    def close(self) -> None:
        self._conn.close()

    def create_investigation(
        self,
        *,
        id: UUID,
        incident_id: UUID,
        stage: str,
        state_json: str,
        created_at: datetime,
        updated_at: datetime,
    ) -> dict[str, Any]:
        """Create a new investigation record."""
        self._conn.execute(
            """
            INSERT INTO investigations
                (id, incident_id, stage, state_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(id),
                str(incident_id),
                stage,
                state_json,
                created_at.isoformat(),
                updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return self.get_investigation(id)  # type: ignore[return-value]

    def get_investigation(self, investigation_id: UUID) -> dict[str, Any] | None:
        """Get an investigation by ID."""
        row = self._conn.execute(
            "SELECT * FROM investigations WHERE id = ?",
            (str(investigation_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_investigation(row)

    def get_by_incident_id(self, incident_id: UUID) -> dict[str, Any] | None:
        """Get an investigation by incident ID."""
        row = self._conn.execute(
            "SELECT * FROM investigations WHERE incident_id = ?",
            (str(incident_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_investigation(row)

    def update_investigation(
        self,
        *,
        investigation_id: UUID,
        stage: str,
        state_json: str,
        updated_at: datetime,
    ) -> dict[str, Any]:
        """Update an existing investigation."""
        self._conn.execute(
            """
            UPDATE investigations
            SET stage = ?, state_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (stage, state_json, updated_at.isoformat(), str(investigation_id)),
        )
        self._conn.commit()
        return self.get_investigation(investigation_id)  # type: ignore[return-value]

    def _row_to_investigation(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to an investigation dict."""
        return {
            "id": UUID(row["id"]),
            "incident_id": UUID(row["incident_id"]),
            "stage": row["stage"],
            "state_json": row["state_json"],
            "created_at": datetime.fromisoformat(row["created_at"]),
            "updated_at": datetime.fromisoformat(row["updated_at"]),
        }


class EvidenceRepository:
    """Data access layer for forensic evidence."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = get_connection(db_path)
        initialize_database(self._conn)

    def close(self) -> None:
        self._conn.close()

    def create_evidence(
        self,
        *,
        id: UUID,
        incident_id: UUID,
        source_type: str,
        source_reference: str,
        content: str,
        timestamp: datetime | None,
        metadata: dict[str, Any],
        created_at: datetime,
    ) -> dict[str, Any]:
        self._conn.execute(
            """
            INSERT INTO evidence
                (id, incident_id, source_type, source_reference,
                 content, timestamp, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(id),
                str(incident_id),
                source_type,
                source_reference,
                content,
                timestamp.isoformat() if timestamp else None,
                json.dumps(metadata),
                created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return self.get_evidence(id)  # type: ignore[return-value]

    def get_evidence(self, evidence_id: UUID) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM evidence WHERE id = ?", (str(evidence_id),)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_evidence(row)

    def list_for_incident(self, incident_id: UUID) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM evidence WHERE incident_id = ? ORDER BY created_at",
            (str(incident_id),),
        ).fetchall()
        return [self._row_to_evidence(r) for r in rows]

    def _row_to_evidence(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": UUID(row["id"]),
            "incident_id": UUID(row["incident_id"]),
            "source_type": row["source_type"],
            "source_reference": row["source_reference"],
            "content": row["content"],
            "timestamp": (
                datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None
            ),
            "metadata": json.loads(row["metadata_json"]),
            "created_at": datetime.fromisoformat(row["created_at"]),
        }


class FindingRepository:
    """Data access layer for agent findings."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = get_connection(db_path)
        initialize_database(self._conn)

    def close(self) -> None:
        self._conn.close()

    def create_finding(
        self,
        *,
        id: UUID,
        incident_id: UUID,
        agent_name: str,
        finding_type: str,
        summary: str,
        confidence: float,
        evidence_ids: list[UUID],
        created_at: datetime,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        self._conn.execute(
            """
            INSERT INTO agent_findings
                (id, incident_id, agent_name, finding_type, summary,
                 confidence, evidence_ids_json, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(id),
                str(incident_id),
                agent_name,
                finding_type,
                summary,
                confidence,
                json.dumps([str(eid) for eid in evidence_ids]),
                created_at.isoformat(),
                json.dumps(metadata),
            ),
        )
        self._conn.commit()
        return self.get_finding(id)  # type: ignore[return-value]

    def get_finding(self, finding_id: UUID) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM agent_findings WHERE id = ?", (str(finding_id),)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_finding(row)

    def list_for_incident(self, incident_id: UUID) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM agent_findings WHERE incident_id = ? ORDER BY created_at",
            (str(incident_id),),
        ).fetchall()
        return [self._row_to_finding(r) for r in rows]

    def _row_to_finding(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": UUID(row["id"]),
            "incident_id": UUID(row["incident_id"]),
            "agent_name": row["agent_name"],
            "finding_type": row["finding_type"],
            "summary": row["summary"],
            "confidence": row["confidence"],
            "evidence_ids": [
                UUID(eid) for eid in json.loads(row["evidence_ids_json"])
            ],
            "created_at": datetime.fromisoformat(row["created_at"]),
            "metadata": json.loads(row["metadata_json"]),
        }


class RCARepository:
    """Data access layer for RCA reports."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = get_connection(db_path)
        initialize_database(self._conn)

    def close(self) -> None:
        self._conn.close()

    def create_rca(
        self,
        *,
        id: UUID,
        incident_id: UUID,
        report_json: str,
        created_at: datetime,
        updated_at: datetime,
    ) -> dict[str, Any]:
        self._conn.execute(
            """
            INSERT INTO rca_reports
                (id, incident_id, report_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(id),
                str(incident_id),
                report_json,
                created_at.isoformat(),
                updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return self.get_rca(id)  # type: ignore[return-value]

    def get_rca(self, rca_id: UUID) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM rca_reports WHERE id = ?", (str(rca_id),)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_rca(row)

    def get_by_incident_id(self, incident_id: UUID) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM rca_reports WHERE incident_id = ?",
            (str(incident_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_rca(row)

    def update_rca(
        self,
        *,
        rca_id: UUID,
        report_json: str,
        updated_at: datetime,
    ) -> dict[str, Any]:
        self._conn.execute(
            "UPDATE rca_reports SET report_json = ?, updated_at = ? WHERE id = ?",
            (report_json, updated_at.isoformat(), str(rca_id)),
        )
        self._conn.commit()
        return self.get_rca(rca_id)  # type: ignore[return-value]

    def _row_to_rca(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": UUID(row["id"]),
            "incident_id": UUID(row["incident_id"]),
            "report_json": row["report_json"],
            "created_at": datetime.fromisoformat(row["created_at"]),
            "updated_at": datetime.fromisoformat(row["updated_at"]),
        }


class RemediationRepository:
    """Data access layer for remediation proposals."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = get_connection(db_path)
        initialize_database(self._conn)

    def close(self) -> None:
        self._conn.close()

    def create_proposal(
        self,
        *,
        id: UUID,
        incident_id: UUID,
        rca_id: UUID,
        type: str,
        title: str,
        description: str,
        rationale: str,
        expected_effect: str,
        risks: list[str],
        prerequisites: list[str],
        commands: list[str],
        patch_summary: str,
        evidence_ids: list[UUID],
        requires_approval: bool,
        status: str,
        created_at: datetime,
    ) -> dict[str, Any]:
        self._conn.execute(
            """
            INSERT INTO remediation_proposals
                (id, incident_id, rca_id, type, title, description,
                 rationale, expected_effect, risks_json, prerequisites_json,
                 commands_json, patch_summary, evidence_ids_json,
                 requires_approval, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(id),
                str(incident_id),
                str(rca_id),
                type,
                title,
                description,
                rationale,
                expected_effect,
                json.dumps(risks),
                json.dumps(prerequisites),
                json.dumps(commands),
                patch_summary,
                json.dumps([str(eid) for eid in evidence_ids]),
                1 if requires_approval else 0,
                status,
                created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return self.get_proposal(id)  # type: ignore[return-value]

    def get_proposal(self, proposal_id: UUID) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM remediation_proposals WHERE id = ?",
            (str(proposal_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_proposal(row)

    def list_for_incident(self, incident_id: UUID) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM remediation_proposals WHERE incident_id = ? ORDER BY created_at",
            (str(incident_id),),
        ).fetchall()
        return [self._row_to_proposal(r) for r in rows]

    def update_status(
        self,
        *,
        proposal_id: UUID,
        status: str,
    ) -> dict[str, Any]:
        self._conn.execute(
            "UPDATE remediation_proposals SET status = ? WHERE id = ?",
            (status, str(proposal_id)),
        )
        self._conn.commit()
        return self.get_proposal(proposal_id)  # type: ignore[return-value]

    def _row_to_proposal(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": UUID(row["id"]),
            "incident_id": UUID(row["incident_id"]),
            "rca_id": UUID(row["rca_id"]),
            "type": row["type"],
            "title": row["title"],
            "description": row["description"],
            "rationale": row["rationale"],
            "expected_effect": row["expected_effect"],
            "risks": json.loads(row["risks_json"]),
            "prerequisites": json.loads(row["prerequisites_json"]),
            "commands": json.loads(row["commands_json"]),
            "patch_summary": row["patch_summary"],
            "evidence_ids": [
                UUID(eid) for eid in json.loads(row["evidence_ids_json"])
            ],
            "requires_approval": bool(row["requires_approval"]),
            "status": row["status"],
            "created_at": datetime.fromisoformat(row["created_at"]),
        }


class ApprovalRepository:
    """Data access layer for approvals."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = get_connection(db_path)
        initialize_database(self._conn)

    def close(self) -> None:
        self._conn.close()

    def create_approval(
        self,
        *,
        id: UUID,
        remediation_id: UUID,
        incident_id: UUID,
        status: str,
        approved_by: str | None,
        created_at: datetime,
        decided_at: datetime | None,
    ) -> dict[str, Any]:
        self._conn.execute(
            """
            INSERT INTO approvals
                (id, remediation_id, incident_id, status, approved_by,
                 created_at, decided_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(id),
                str(remediation_id),
                str(incident_id),
                status,
                approved_by,
                created_at.isoformat(),
                decided_at.isoformat() if decided_at else None,
            ),
        )
        self._conn.commit()
        return self.get_approval(id)  # type: ignore[return-value]

    def get_approval(self, approval_id: UUID) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE id = ?", (str(approval_id),)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_approval(row)

    def get_by_remediation_id(self, remediation_id: UUID) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE remediation_id = ?",
            (str(remediation_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_approval(row)

    def update_approval(
        self,
        *,
        approval_id: UUID,
        status: str,
        approved_by: str,
        decided_at: datetime,
    ) -> dict[str, Any]:
        self._conn.execute(
            """
            UPDATE approvals
            SET status = ?, approved_by = ?, decided_at = ?
            WHERE id = ?
            """,
            (status, approved_by, decided_at.isoformat(), str(approval_id)),
        )
        self._conn.commit()
        return self.get_approval(approval_id)  # type: ignore[return-value]

    def _row_to_approval(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": UUID(row["id"]),
            "remediation_id": UUID(row["remediation_id"]),
            "incident_id": UUID(row["incident_id"]),
            "status": row["status"],
            "approved_by": row["approved_by"],
            "created_at": datetime.fromisoformat(row["created_at"]),
            "decided_at": (
                datetime.fromisoformat(row["decided_at"])
                if row["decided_at"]
                else None
            ),
        }
