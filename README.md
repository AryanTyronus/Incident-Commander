# Incident Commander — Phase 1

A production-quality foundation for incident management with webhook ingestion from PagerDuty and Sentry.

## Phase 1 Scope

Phase 1 implements:

- FastAPI application scaffolding
- Pydantic v2 schemas with strict validation
- SQLite persistence with parameterized queries
- Repository/service layer separation
- Incident state machine with enforced transitions
- PagerDuty and Sentry webhook ingestion
- Webhook deduplication (idempotent delivery)
- Raw payload preservation as immutable evidence
- Comprehensive deterministic pytest suite

**Not implemented in Phase 1:** Strands agents, Ollama/Qwen, ChromaDB, RCA, remediation, frontend, or any agent orchestration.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  FastAPI Application             │
├──────────────┬──────────────────────────────────┤
│  POST /api/  │  POST /api/webhooks/             │
│  incidents   │  pagerduty  |  sentry            │
├──────────────┴──────────────────────────────────┤
│              IncidentService                    │
│  (business logic, state machine, dedup)         │
├─────────────────────────────────────────────────┤
│            IncidentRepository                   │
│  (parameterized SQL, no raw SQL in routes)      │
├─────────────────────────────────────────────────┤
│              SQLite Database                    │
│  incidents  |  incident_events                  │
└─────────────────────────────────────────────────┘
```

## Setup

### Prerequisites

- Python 3.13+
- pip or uv

### Installation

```bash
pip install -e ".[dev]"
```

### Environment Variables

| Variable         | Default                    | Description           |
|------------------|----------------------------|-----------------------|
| `DATABASE_PATH`  | `data/incidents.db`        | SQLite database path  |
| `API_HOST`       | `0.0.0.0`                  | API host              |
| `API_PORT`       | `8000`                     | API port              |
| `ENVIRONMENT`    | `development`              | Runtime environment   |

Copy `.env.example` to `.env` and modify as needed.

### Database

The SQLite database is created automatically at startup under `data/`. No migrations required.

## Running

```bash
# Start the API server
uvicorn backend.app.main:app --reload

# Or with custom settings
DATABASE_PATH=data/custom.db API_PORT=9000 uvicorn backend.app.main:app --reload
```

## API Endpoints

| Method | Path                          | Description                    |
|--------|-------------------------------|--------------------------------|
| GET    | `/health`                     | Health check                   |
| POST   | `/api/incidents`              | Create a manual/raw incident   |
| GET    | `/api/incidents`              | List incidents (paginated)     |
| GET    | `/api/incidents/{id}`         | Get a specific incident        |
| PATCH  | `/api/incidents/{id}/status`  | Transition incident status     |
| POST   | `/api/webhooks/pagerduty`     | Ingest PagerDuty webhook       |
| POST   | `/api/webhooks/sentry`        | Ingest Sentry webhook          |

### Sample Requests

```bash
# Create an incident
curl -X POST http://localhost:8000/api/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "source": "MANUAL",
    "title": "Database connection pool exhausted",
    "severity": "SEV1",
    "service": "payment-service",
    "environment": "production",
    "description": "All connections in use"
  }'

# List incidents
curl http://localhost:8000/api/incidents

# Get a specific incident
curl http://localhost:8000/api/incidents/{incident-id}

# Transition status
curl -X PATCH http://localhost:8000/api/incidents/{incident-id}/status \
  -H "Content-Type: application/json" \
  -d '{"status": "TRIAGING"}'

# PagerDuty webhook
curl -X POST http://localhost:8000/api/webhooks/pagerduty \
  -H "Content-Type: application/json" \
  -d '{"id": "evt-123", "event": {"data": {"title": "Alert", "urgency": "high", "service": {"summary": "api-gw"}}}}'

# Sentry webhook
curl -X POST http://localhost:8000/api/webhooks/sentry \
  -H "Content-Type: application/json" \
  -d '{"id": "sentry-456", "message": "TypeError in render()", "level": "error", "project": {"name": "web-app"}}'
```

## State Machine

```
RECEIVED → TRIAGING → INVESTIGATING → SYNTHESIZING → AWAITING_APPROVAL → RESOLVED
                ↓              ↓              ↓                ↓
              FAILED         FAILED         FAILED           FAILED
```

Invalid transitions return HTTP 409 Conflict.

## Testing

```bash
# Run all tests
pytest -q

# Run with verbose output
pytest -v

# Run specific test file
pytest backend/tests/test_incidents_api.py
```

## Static Checks

```bash
# Syntax check
python -m compileall backend

# Linting (if ruff installed)
ruff check .
```

## Project Structure

```
incident-commander/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Environment configuration
│   │   ├── db.py                # SQLite setup
│   │   ├── dependencies.py      # FastAPI dependency injection
│   │   ├── repositories.py      # Data access layer
│   │   ├── api/
│   │   │   ├── incidents.py     # Incident CRUD routes
│   │   │   └── webhooks.py      # PagerDuty/Sentry webhooks
│   │   ├── models/
│   │   │   ├── enums.py         # IncidentSource, Severity, Status
│   │   │   └── schemas.py       # Pydantic request/response models
│   │   └── services/
│   │       └── incident_service.py  # Business logic & state machine
│   └── tests/
│       ├── conftest.py          # Test fixtures & helper payloads
│       ├── test_incidents_api.py
│       ├── test_webhooks.py
│       ├── test_incident_service.py
│       └── test_database.py
├── data/                        # SQLite database storage
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

## Phase 2 Roadmap (Not Implemented)

- Strands agent orchestration
- Ollama/Qwen integration
- ChromaDB vector storage
- Root cause analysis
- Automated remediation
- Frontend dashboard
