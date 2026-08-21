from __future__ import annotations

import os
import tempfile
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture()
def tmp_db(monkeypatch: pytest.MonkeyPatch) -> Generator[str]:
    """Provide a temporary SQLite database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    monkeypatch.setenv("DATABASE_PATH", db_path)
    # Reset the settings singleton to pick up the new env var
    import backend.app.config as cfg
    monkeypatch.setattr(cfg.settings, "DATABASE_PATH", db_path)
    yield db_path
    os.unlink(db_path)


@pytest.fixture()
def client(tmp_db: str) -> Generator[TestClient]:
    """Provide a FastAPI test client with a temporary database."""
    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------
# Helper payloads
# ------------------------------------------------------------------


def make_pagerduty_payload(
    event_id: str = "pd-event-001",
    title: str = "API Gateway 5xx Spike",
    urgency: str = "high",
    service_name: str = "api-gateway",
) -> dict:
    return {
        "id": event_id,
        "event": {
            "event_type": "incident.triggered",
            "data": {
                "id": event_id,
                "title": title,
                "urgency": urgency,
                "service": {"summary": service_name, "id": "SVC123"},
                "body": {
                    "type": "incident_body",
                    "details": {
                        "description": "Elevated 5xx error rate detected",
                        "environment": "production",
                    },
                },
                "description": "Elevated 5xx error rate detected",
            },
        },
    }


def make_sentry_payload(
    event_id: str = "sentry-event-001",
    message: str = "TypeError: Cannot read property 'id' of undefined",
    level: str = "error",
    project_name: str = "web-frontend",
) -> dict:
    return {
        "id": event_id,
        "eventID": event_id,
        "message": message,
        "culprit": "src/components/Dashboard.tsx",
        "level": level,
        "project": {"name": project_name, "slug": "web-frontend"},
        "tags": {"environment": "production"},
        "stacktrace": {
            "frames": [
                {
                    "function": "render",
                    "filename": "src/components/Dashboard.tsx",
                    "abs_path": "/app/src/components/Dashboard.tsx",
                },
                {
                    "function": "fetchUserData",
                    "filename": "src/api/users.ts",
                    "abs_path": "/app/src/api/users.ts",
                },
            ],
        },
    }
