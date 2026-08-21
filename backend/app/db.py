from __future__ import annotations

import sqlite3
from pathlib import Path


def get_connection(db_path: str) -> sqlite3.Connection:
    """Create a new SQLite connection with foreign keys enabled."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    """Create tables if they do not exist. Safe to run repeatedly."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id              TEXT PRIMARY KEY,
            source          TEXT NOT NULL,
            title           TEXT NOT NULL,
            severity        TEXT NOT NULL,
            service         TEXT NOT NULL,
            environment     TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'RECEIVED',
            description     TEXT NOT NULL DEFAULT '',
            stack_traces    TEXT NOT NULL DEFAULT '[]',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            raw_payload     TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS incident_events (
            id                  TEXT PRIMARY KEY,
            incident_id         TEXT NOT NULL,
            event_type          TEXT NOT NULL,
            source              TEXT,
            external_event_id   TEXT,
            old_status          TEXT,
            new_status          TEXT,
            payload             TEXT NOT NULL DEFAULT '{}',
            created_at          TEXT NOT NULL,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_webhook_dedup
            ON incident_events(source, external_event_id)
            WHERE external_event_id IS NOT NULL;

        CREATE TABLE IF NOT EXISTS agent_runs (
            id              TEXT PRIMARY KEY,
            incident_id     TEXT NOT NULL,
            agent_name      TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'PENDING',
            started_at      TEXT,
            completed_at    TEXT,
            input_json      TEXT NOT NULL DEFAULT '{}',
            output_json     TEXT,
            error           TEXT,
            metadata_json   TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );

        CREATE TABLE IF NOT EXISTS investigations (
            id              TEXT PRIMARY KEY,
            incident_id     TEXT NOT NULL UNIQUE,
            stage           TEXT NOT NULL,
            state_json      TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );

        CREATE TABLE IF NOT EXISTS evidence (
            id                  TEXT PRIMARY KEY,
            incident_id         TEXT NOT NULL,
            source_type         TEXT NOT NULL,
            source_reference    TEXT NOT NULL,
            content             TEXT NOT NULL,
            timestamp           TEXT,
            metadata_json       TEXT NOT NULL DEFAULT '{}',
            created_at          TEXT NOT NULL,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );

        CREATE TABLE IF NOT EXISTS agent_findings (
            id                  TEXT PRIMARY KEY,
            incident_id         TEXT NOT NULL,
            agent_name          TEXT NOT NULL,
            finding_type        TEXT NOT NULL,
            summary             TEXT NOT NULL,
            confidence          REAL NOT NULL,
            evidence_ids_json   TEXT NOT NULL DEFAULT '[]',
            created_at          TEXT NOT NULL,
            metadata_json       TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );

        CREATE TABLE IF NOT EXISTS rca_reports (
            id              TEXT PRIMARY KEY,
            incident_id     TEXT NOT NULL UNIQUE,
            report_json     TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );

        CREATE TABLE IF NOT EXISTS remediation_proposals (
            id                  TEXT PRIMARY KEY,
            incident_id         TEXT NOT NULL,
            rca_id              TEXT NOT NULL,
            type                TEXT NOT NULL,
            title               TEXT NOT NULL,
            description         TEXT NOT NULL,
            rationale           TEXT NOT NULL DEFAULT '',
            expected_effect     TEXT NOT NULL DEFAULT '',
            risks_json          TEXT NOT NULL DEFAULT '[]',
            prerequisites_json  TEXT NOT NULL DEFAULT '[]',
            commands_json       TEXT NOT NULL DEFAULT '[]',
            patch_summary       TEXT NOT NULL DEFAULT '',
            evidence_ids_json   TEXT NOT NULL DEFAULT '[]',
            requires_approval   INTEGER NOT NULL DEFAULT 1,
            status              TEXT NOT NULL DEFAULT 'PROPOSED',
            created_at          TEXT NOT NULL,
            FOREIGN KEY (incident_id) REFERENCES incidents(id),
            FOREIGN KEY (rca_id) REFERENCES rca_reports(id)
        );

        CREATE TABLE IF NOT EXISTS approvals (
            id                  TEXT PRIMARY KEY,
            remediation_id      TEXT NOT NULL,
            incident_id         TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'PENDING',
            approved_by         TEXT,
            created_at          TEXT NOT NULL,
            decided_at          TEXT,
            FOREIGN KEY (remediation_id) REFERENCES remediation_proposals(id),
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );
        """
    )
    conn.commit()
