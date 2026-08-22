# Incident Commander

> **Autonomous forensic investigation and safe remediation planning for distributed-system incidents.**

Incident Commander is a deterministic, multi-agent incident investigation platform designed to reduce the cognitive load of SREs during high-severity production incidents.

It bridges the gap between raw incident alerts and safe remediation by combining:

- Deterministic forensic analysis
- Multi-agent investigation
- Evidence-backed root-cause analysis
- Mathematical confidence scoring
- Historical runbook retrieval
- Remediation planning
- Human-in-the-loop approval
- Real-time WebSocket event streaming
- A React-based incident command dashboard

**Incident Commander does not automatically execute production remediation commands.**

Every remediation proposal requires explicit human approval.

---

## Core Architecture

```text
                         INCIDENT
                            │
                            ▼
                  ┌───────────────────┐
                  │ Incident Ingestion │
                  │ FastAPI            │
                  └─────────┬─────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Incident Commander  │
                 │ Orchestrator        │
                 └─────────┬───────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌───────────┐ ┌───────────┐
        │   Log    │ │    Git    │ │  Runbook  │
        │  Triage  │ │ Forensics │ │    RAG    │
        └────┬─────┘ └─────┬─────┘ └─────┬─────┘
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                  ┌─────────────────┐
                  │ Evidence +      │
                  │ Agent Findings  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Timeline +      │
                  │ Contradictions │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Deterministic   │
                  │ Confidence      │
                  │ Engine          │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ RCA Synthesis   │
                  │ LLM + Fallback  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Remediation     │
                  │ Planner         │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Safety          │
                  │ Validator       │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ HUMAN APPROVAL  │
                  │      GATE        │
                  └────────┬────────┘
                           │
                    APPROVE / REJECT
                           │
                           ▼
                  No automatic execution
```

---

# Features

## 1. Incident Management
Incident Commander supports incident ingestion and lifecycle management through FastAPI.

Supported sources include:

- Manual incidents
- PagerDuty webhooks
- Sentry webhooks
- Deterministic demo incidents
Incident state transitions are enforced through a state machine.

```
RECEIVED
    │
    ▼
TRIAGING
    │
    ▼
INVESTIGATING
    │
    ▼
SYNTHESIZING
    │
    ▼
AWAITING_APPROVAL
    │
    ▼
RESOLVED
```
Failed investigations are persisted as `FAILED` rather than silently disappearing.

---

# 2. Durable Investigation State
Investigation state is persisted in SQLite.

Investigation lifecycle:

```
NOT_STARTED
     │
     ▼
PLANNING
     │
     ▼
EXECUTING
     │
     ▼
AGGREGATING
     │
     ├──────────────► FAILED
     │
     ▼
COMPLETED
```
The state includes:

- Current investigation stage
- Active agent runs
- Completed agent runs
- Failed agent runs
- Findings
- Investigation timestamps
- Error information
- Agent references
Investigation requests return immediately with:

```
202 Accepted
```
The actual investigation executes in the background.

---

# 3. Multi-Agent Forensic Investigation
Incident Commander uses specialized agents rather than one unconstrained autonomous agent.

## Log Triage Agent
Performs deterministic analysis of incident logs.

Capabilities:

- Error detection
- Error burst detection
- Pattern clustering
- Stack-trace extraction
- Configurable time-window analysis

---

## Git Forensics Agent
Investigates source-code changes around the incident window.

Capabilities:

- Recent commit inspection
- Commit metadata extraction
- Diff analysis
- Candidate deployment detection
- Stack-trace/file correlation
- Line-change correlation
Blocking Git subprocess operations are executed off the async event loop.

---

## Runbook & RAG Agent
Retrieves relevant operational knowledge from:

- Runbooks
- Postmortems
- Incident playbooks
- Historical operational documentation
ChromaDB provides local vector storage.

The system supports:

```
Documents
   ↓
Chunking
   ↓
Embedding
   ↓
ChromaDB
   ↓
Semantic Search
   ↓
Runbook Evidence
```

---

# 4. Evidence-First Architecture
Incident Commander separates facts from reasoning.

The system distinguishes:

### Observed Facts
Directly supported by collected evidence.

Examples:

- A deployment occurred at a specific timestamp.
- A specific error appeared in logs.
- A particular file changed in a commit.

### Inferred Hypotheses
Conclusions derived from multiple pieces of evidence.

Examples:

- A deployment likely introduced a validation regression.
- A specific code path is the likely root cause.

### Open Uncertainties
Information that cannot be established from available evidence.

This prevents the system from presenting speculation as fact.

---

# 5. Evidence & Provenance
Evidence is persisted in SQLite before it can be referenced by RCA or remediation components.

Evidence types include:

```
LOG
GIT_COMMIT
GIT_DIFF
STACK_TRACE
RUNBOOK
POSTMORTEM
```
Each evidence record contains provenance information including:

- Incident ID
- Source type
- Source reference
- Content
- Timestamp
- Metadata
- Creation timestamp
Agent findings reference evidence IDs rather than inventing unsupported evidence.

---

# 6. Deterministic Root Cause Analysis
RCA synthesis combines deterministic analysis with an LLM.

The LLM is responsible for synthesizing hypotheses from collected evidence.

The LLM does **not** determine the final confidence score.

The pipeline is:

```
Agent Findings
      │
      ▼
Evidence Validation
      │
      ▼
Timeline Construction
      │
      ▼
Contradiction Detection
      │
      ▼
Deterministic Confidence Engine
      │
      ▼
LLM Hypothesis Synthesis
      │
      ▼
Root Cause Analysis
```
Malformed LLM output falls back to deterministic behavior rather than being blindly trusted.

---

# 7. Mathematical Confidence Scoring
Confidence is calculated independently of the LLM.

The current scoring model is:

$$
Score =
(Support \times 0.30)
+
(Temporal \times 0.20)
+
(Correlation \times 0.20)
+
(Runbook \times 0.10)
-
(Contradictions \times 0.15)
-
(MissingEvidence \times 0.10)
$$

Scores are normalized to the range:

$$
0 \leq Score \leq 1
$$

Confidence bands:

| Score | Classification |
|-------|-----------------|
| 0.00 – 0.39 | LOW |
| 0.40 – 0.69 | MEDIUM |
| 0.70 – 0.89 | HIGH |
| 0.90 – 1.00 | VERY_HIGH |

This allows Incident Commander to explicitly communicate uncertainty instead of presenting every RCA as certain.

---

# 8. Contradiction Detection
The system actively looks for evidence that disagrees with a hypothesis.

Current contradiction checks include:

### Temporal contradictions
Evidence timestamps differ beyond the configured tolerance.

### Git/log contradictions
A suspected commit occurs after the observed failure began.

### Finding confidence contradictions
Different agents provide materially different confidence levels for related findings.

Contradictions reduce the deterministic confidence score.

---

# 9. Remediation Planning
Incident Commander generates remediation proposals without executing them.

Supported proposal types include:

- Rollback plans
- Patch plans
- Investigation/fallback proposals
A proposal contains:

- Title
- Description
- Rationale
- Expected effect
- Risks
- Prerequisites
- Commands
- Patch summary
- Supporting evidence
- Approval requirement
Example:

```
RCA
 │
 ▼
Remediation Planner
 │
 ├── Rollback proposal
 │
 ├── Patch proposal
 │
 └── Investigation proposal
 │
 ▼
Safety Validator
 │
 ▼
Human Approval
```

---

# 10. Remediation Safety
Remediation commands are treated as untrusted data.

The safety layer rejects dangerous patterns including:

```
rm -rf /
sudo
curl | sh
wget | sh
command substitution
backticks
path traversal
chmod 777
dd
```
The safety validator runs before a proposal reaches the approval interface.

### Important Safety Guarantee
Incident Commander does **not** automatically execute remediation commands.

The current system is a:

> **Forensic investigation + verified remediation planning system**

rather than an autonomous production execution engine.

---

# 11. Human-in-the-Loop Governance
Every remediation proposal requires explicit human authorization.

Approval state machine:

```
PENDING
   │
   ├──────────► APPROVED
   │
   └──────────► REJECTED
```
Terminal states cannot be changed.

Each decision records:

- Engineer ID
- Decision
- Timestamp
- Remediation ID
- Incident ID
Duplicate decisions are rejected.

Example:

```
POST /api/remediations/{id}/approve?approved_by=engineer-123
```
or:

```
POST /api/remediations/{id}/reject?rejected_by=engineer-123
```
Approval means:

> The remediation proposal has been explicitly authorized.

It does **not** mean the system executes the command.

---

# 12. Real-Time Event Streaming
The frontend receives investigation events through WebSockets.

Endpoint:

```
WS /api/incidents/{incident_id}/stream
```
Events are:

- Persisted to the SQLite audit trail
- Published through an in-process event publisher
- Broadcast to WebSocket subscribers
Events use monotonically increasing sequence numbers.

This allows the frontend to prevent duplicate events and replay events deterministically.

Architecture:

```
Investigation
     │
     ▼
Domain Event
     │
     ▼
EventPublisher
     │
     ├──────────────► SQLite Audit
     │
     └──────────────► WebSocket
                            │
                            ▼
                       React UI
```
The Vite development proxy enables WebSocket upgrades on `/api`.

---

# 13. React Dashboard
The frontend is built with:

- React 19
- TypeScript
- Vite
- React Router
- Vitest
- React Testing Library
The dashboard provides:

### Incident Dashboard

- Incident list
- Severity
- Status
- Service
- Environment
- Demo incident replay

### Incident Detail

- Incident header
- Investigation status
- Agent execution graph
- Live event timeline
- Evidence panel
- RCA view
- Confidence visualization
- Remediation proposals
- HITL approval/rejection controls

---

# 14. Demo Incident
A deterministic demo incident is available through:

```
POST /api/demo/incidents
```
The demo represents:

> **Payment service outage — validation regression**

It includes deterministic evidence such as:

- Log errors
- Stack traces
- Git commit
- Git diff
This provides a reproducible demonstration without requiring external production infrastructure.

---

# 15. Technology Stack

| Layer | Technology | Language |
|-------|-----------|----------|
| Python | 3.13 | |
| Backend | FastAPI | |
| Data Validation | Pydantic v2 | |
| Database | SQLite | |
| Vector Store | ChromaDB | |
| LLM | Ollama / Qwen2.5-Coder 7B | |
| Agent Architecture | Strands-compatible runtime | |
| Frontend | React 19 | |
| Frontend Language | TypeScript | |
| Build Tool | Vite | |
| Testing | pytest + Vitest | |
| UI Testing | React Testing Library | |
| Linting | Ruff | |
| Transport | HTTP + WebSocket | |

The system is designed to run locally without paid external APIs.

---

# 16. Database Architecture
SQLite stores structured application state and provenance.

Core relationships:

```
incidents
    │
    ├── investigation state
    │
    ├── evidence
    │      │
    │      └── agent findings
    │
    ├── RCA report
    │       │
    │       └── remediation proposals
    │                    │
    │                    └── approvals
    │
    └── incident events
```
The database path is resolved relative to the repository root so launching the backend from either:

```
~/Desktop/incident-commander
```
or:

```
~/Desktop/incident-commander/backend
```
uses the same database.

---

# 17. API Overview

## Health

```
GET /health
GET /ready
```
`/ready` verifies required local infrastructure including SQLite and ChromaDB.

---

## Incidents

```
POST   /api/incidents
GET    /api/incidents
GET    /api/incidents/{id}
PATCH  /api/incidents/{id}/status
```

---

## Investigation

```
POST /api/incidents/{id}/investigate
GET  /api/incidents/{id}/investigation
```
Investigation starts asynchronously and returns:

```
202 Accepted
```

---

## Evidence

```
GET /api/incidents/{id}/evidence
GET /api/incidents/{id}/findings
```

---

## RCA

```
POST /api/incidents/{id}/analyze
GET  /api/incidents/{id}/rca
```
RCA analysis is idempotent. Re-analyzing an incident with an existing RCA does not create duplicate RCA/proposal records or invalidate existing approval decisions.

---

## Remediation

```
GET /api/incidents/{id}/remediation

POST /api/remediations/{id}/approve
POST /api/remediations/{id}/reject
```

---

## Events

```
GET /api/incidents/{id}/events

WS /api/incidents/{id}/stream
```

---

## Demo

```
POST /api/demo/incidents
```

---

# 18. Local Setup

## Prerequisites

- Python 3.13+
- Node.js 18+
- npm
- Ollama
- Git

---

## Clone

```
git clone <your-repository-url>
cd incident-commander
```

---

## Backend Environment
Create or activate the virtual environment:

```
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
```
Install dependencies:

```
pip install -r ../requirements.txt
```
Alternatively:

```
pip install -e ".[dev]"
```

---

# 19. Ollama Setup
Install Ollama and make sure the local server is running.

Pull the configured model:

```
ollama pull qwen2.5-coder:7b
```
Verify:

```
ollama list
```
Test the model:

```
curl http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:7b",
    "prompt": "Return exactly the word OK.",
    "stream": false
  }'
```
The project loads `.env` automatically.

Example:

```
OLLAMA_MODEL=qwen2.5-coder:7b
OLLAMA_BASE_URL=http://localhost:11434
```
Tests use `FakeLLMProvider` and do not require Ollama.

---

# 20. Start the Backend
From the repository root:

```
source backend/.venv/bin/activate

uvicorn backend.app.main:app --reload --port 8000
```
Backend:

```
http://localhost:8000
```
Health check:

```
curl http://localhost:8000/health
```
Readiness:

```
curl http://localhost:8000/ready
```

---

# 21. Start the Frontend
In another terminal:

```
cd frontend
npm install
npm run dev
```
Open:

```
http://localhost:5173
```
The Vite development server proxies `/api` requests and WebSocket connections to the FastAPI backend.

---

# 22. Running the Demo
The recommended demonstration sequence is:

### Step 1 — Replay Demo Incident
Click:

```
Replay Demo Incident
```
A deterministic SEV-1 payment-service incident is created.

### Step 2 — Investigate
Open the incident and click:

```
Investigate
```
The API immediately returns:

```
202 Accepted
```
The investigation runs in the background.

The dashboard receives live events through WebSocket.

Watch the agent graph progress through:

```
Planning
    ↓
Executing
    ↓
Aggregating
    ↓
Completed
```

### Step 3 — Analyze
Click:

```
Analyze (RCA)
```
The system produces:

- Root-cause hypotheses
- Observed facts
- Uncertainties
- Contradictions
- Confidence score
- Confidence band
- Supporting evidence

### Step 4 — Review Remediation
The system generates safe proposals such as:

```
Rollback
Patch
Investigation
```

### Step 5 — Human Approval
Enter an engineer ID.

Choose:

```
Approve
```
or:

```
Reject
```
The decision is persisted.

No production command is automatically executed.

---

# 23. Testing
The project contains comprehensive backend and frontend tests.

## Backend
From the repository root:

```
source backend/.venv/bin/activate
pytest -q
```
Current verified result:

```
322 passed
```

---

## Frontend

```
cd frontend
npm test -- --run
```
Current verified result:

```
115 passed
```

---

## Static Checks
Backend syntax:

```
python -m compileall backend
```
Lint:

```
ruff check .
```
Frontend build:

```
cd frontend
npm run build
```

---

# 24. Verification Status
Current manually verified end-to-end flow:

```
✓ Demo incident creation
✓ Incident loading
✓ WebSocket connection
✓ Investigation HTTP 202
✓ Background investigation
✓ Agent execution
✓ Investigation persistence
✓ Evidence collection
✓ RCA synthesis
✓ Deterministic confidence scoring
✓ Remediation generation
✓ Remediation safety validation
✓ HITL rejection
✓ HITL approval
✓ Duplicate decision protection
✓ Idempotent RCA analysis
✓ Repeat analysis after approval
✓ No automatic production execution
```
Automated verification:

```
Backend tests:    322 passed
Frontend tests:   115 passed
Ruff:             clean
Compileall:       clean
Frontend build:   clean
```

---

# 25. Security & Safety Principles
Incident Commander follows several hard architectural constraints.

### No blind autonomous execution
The system never directly executes generated remediation commands.

### Evidence before inference
RCA hypotheses must reference collected evidence.

### Deterministic confidence
The LLM cannot arbitrarily assign its own confidence score.

### Human approval
Every remediation proposal requires explicit human authorization.

### Dangerous command rejection
Known dangerous shell patterns are rejected before reaching the approval layer.

### No secrets in frontend
The React application contains no API keys or production credentials.

### Local-first execution
The complete development/demo stack can run locally without paid APIs.

---

# 26. Project Structure

```
incident-commander/
│
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── commander.py
│   │   │   ├── log_triage.py
│   │   │   ├── git_forensics.py
│   │   │   ├── runbook.py
│   │   │   └── registry.py
│   │   │
│   │   ├── analysis/
│   │   │   ├── rca.py
│   │   │   ├── confidence.py
│   │   │   ├── contradictions.py
│   │   │   └── timeline.py
│   │   │
│   │   ├── approval/
│   │   │   ├── policies.py
│   │   │   └── service.py
│   │   │
│   │   ├── api/
│   │   │   ├── incidents.py
│   │   │   ├── webhooks.py
│   │   │   ├── stream.py
│   │   │   ├── health.py
│   │   │   └── demo.py
│   │   │
│   │   ├── events/
│   │   ├── llm/
│   │   ├── models/
│   │   ├── orchestration/
│   │   ├── remediation/
│   │   ├── retrieval/
│   │   ├── services/
│   │   ├── tools/
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── dependencies.py
│   │   └── main.py
│   │
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── test/
│   │   └── __tests__/
│   ├── package.json
│   └── vite.config.ts
│
├── fixtures/
│   ├── logs/
│   ├── runbooks/
│   └── repos/
│
├── data/
│   └── chroma/
│
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

---

# 27. Design Principles
Incident Commander is built around five principles:

### 1. Facts before conclusions
The system collects evidence before synthesizing hypotheses.

### 2. Determinism before autonomy
Financial-style deterministic controls are applied wherever possible.

### 3. Uncertainty is explicit
Low confidence is a valid result.

### 4. Humans remain accountable
AI can investigate and propose.

Humans authorize remediation.

### 5. Failure must be observable
Investigations, agents, decisions, and state transitions are persisted and streamed as structured events.

---

# 28. Current Limitations
This is a hackathon-grade system rather than a production deployment.

Known limitations include:

- Authentication/authorization is not yet implemented.
- CORS is configured for local development by default.
- WebSocket connections are managed in-process.
- SQLite is intended for local/demo workloads.
- ChromaDB is locally persisted rather than deployed as a distributed vector service.
- Safety validation is pattern-based rather than a complete shell security model.
- Frontend styling is intentionally lightweight.
- The system does not execute approved commands.
Production deployment would require additional controls including:

- Identity and access management
- Audit-grade authorization
- Secrets management
- Distributed persistence
- Production telemetry integrations
- Network isolation
- Command sandboxing
- Stronger policy enforcement
- Operational monitoring

---

# 29. Roadmap
Potential future work:

- Native AWS telemetry integrations
- CloudWatch log ingestion
- AWS CodeDeploy / CodePipeline deployment correlation
- Production-grade vector infrastructure
- Distributed event streaming
- Authentication and RBAC
- Immutable audit logs
- Advanced remediation simulation
- Sandboxed remediation execution
- Automated verification after remediation
- Incident postmortem generation
- Historical incident learning

---

# 30. Hackathon Positioning
Incident Commander is designed for the **AWS AI Agent Hackathon — Professional Agents Track**.

The central idea is not simply:

> "An LLM that investigates an incident."

It is:

> **A deterministic incident investigation system that uses specialized AI agents to gather evidence, mathematically evaluates confidence, proposes safe remediation, and keeps a human in control of production changes.**

The architecture deliberately separates:

```
AI Reasoning
     │
     ▼
Evidence
     │
     ▼
Deterministic Validation
     │
     ▼
Confidence
     │
     ▼
Remediation Proposal
     │
     ▼
Safety Validation
     │
     ▼
Human Approval
```

This separation is the foundation of the system's safety model.

---

# License
See the repository license for project licensing information.
