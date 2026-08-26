# Incident Commander Enterprise — Claude Code Guide

## Mission and non-negotiables

You are working on an autonomous SRE engine for multi-tenant B2B incident diagnosis and triage. Optimize for safe, evidence-backed, auditable changes—not cleverness. Preserve human approval gates for remediation and never turn an investigative capability into an automatic production mutation without an explicit product requirement.

Hard requirements:

- Python 3.13, FastAPI, Pydantic V2, Redis task queue, PostgreSQL.
- React 19, Vite, TypeScript, Tailwind CSS in `frontend/`.
- Async Anthropic/AWS Bedrock integration with strict Pydantic schemas and zero-data-retention compliance.
- No blocking calls on async paths. Use native async clients where available; otherwise isolate synchronous I/O with `await asyncio.to_thread(...)`.
- Strict typing, no bare `except`, explicit error handling, tenant isolation, and tests for security boundaries.
- Never expose secrets, prompts containing customer data, raw incident payloads, or provider responses in logs.

Before changing code, inspect the relevant files, tests, configuration, and call sites. Keep diffs small and explain trade-offs in the final summary.

## Repository map

- `backend/`: Python application and tests.
- `backend/app/`: application modules, API, domain logic, integrations, workers.
- `backend/tests/`: pytest suite.
- `frontend/`: Vite/React/TypeScript application.
- `fixtures/`, `data/`: development/test data; treat all customer-like data as sensitive.
- `scripts/`: repository utilities.
- `pyproject.toml`: Python metadata, Ruff, and pytest configuration.
- `requirements.txt`: runtime dependency pins/constraints.
- `.env.example`: configuration contract; never commit real `.env` files.

Do not infer architecture from names alone. Search for existing patterns and reuse established dependency injection, error models, configuration, and test fixtures.

## Safe development workflow

1. Read the relevant implementation and its complete test file before editing.
2. Identify tenant, authorization, data-retention, async, and failure-mode implications.
3. Make the smallest coherent change; avoid unrelated formatting or dependency upgrades.
4. Add or update tests before declaring the change complete.
5. Run focused checks, then the full applicable checks below.
6. Review the diff for secrets, PII, cross-tenant access, blocking calls, and accidental API contract changes.

Never use production credentials, live customer data, or destructive commands to validate a change. Do not weaken tests, lint rules, type checks, approval gates, or retention controls to make a build pass.

## Backend commands

From the repository root:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
pytest backend/tests/path/to/test_file.py -q
ruff check .
ruff format --check .
uvicorn backend.app.main:app --reload
```

If the actual ASGI import path differs, discover it from the repository rather than guessing. Use `python -m pytest` when the environment does not expose a `pytest` executable.

Before a backend change is complete, run at minimum:

```bash
python -m pytest -q
ruff check .
```

Use a temporary isolated database/Redis service for integration tests. Never run migration or deletion commands against a shared or production database.

## Frontend commands

From `frontend/`:

```bash
npm ci
npm run dev
npm run build
npm run lint
npm test
npm run test:watch
npm run preview
```

The checked-in scripts are authoritative. `npm run build` performs TypeScript project compilation and Vite bundling; `npm run lint` uses Oxlint; `npm test` runs Vitest.

## Python engineering rules

- Use complete type annotations, including return types and public attributes.
- Prefer immutable, explicit data flow and narrow interfaces.
- Use Pydantic V2 models for external/API/LLM boundaries. Configure validation deliberately; do not silently coerce security-sensitive values.
- Use `model_validate`, `model_dump`, and V2 validators consistently with existing code.
- Do not use `Any` to evade a typing problem; use a precise model, `TypedDict`, `Protocol`, or a justified cast.
- Never write `except:`. Catch the narrowest expected exception, preserve context with `raise ... from exc`, and map errors to safe client-facing responses.
- Never leak stack traces, SQL, provider payloads, tokens, tenant identifiers, or incident contents in responses or normal logs.
- Avoid mutable default arguments and hidden global state.
- Keep business logic out of route handlers; use services/use cases with injectable dependencies.

## Async and queue rules

- An `async def` path must not perform blocking filesystem, DNS, SDK, database, Redis, subprocess, or CPU-heavy work directly.
- Prefer async database/Redis/HTTP clients. For unavoidable synchronous libraries, use `await asyncio.to_thread(sync_fn, ...)` and document the boundary.
- Do not call `time.sleep`, synchronous `requests`, blocking SDK methods, or synchronous filesystem APIs from the event loop.
- Propagate cancellation. Do not swallow `asyncio.CancelledError`; clean up in `finally` and re-raise.
- Add timeouts, bounded retries, exponential backoff with jitter, and idempotency where external calls or jobs can repeat.
- Redis jobs must be safe to retry, have explicit ownership/visibility semantics, and not enqueue unbounded work.
- Do not create detached tasks without lifecycle ownership, exception observation, and shutdown handling.

## Multi-tenancy and authorization

Tenant isolation is a security invariant, not an application convention.

- Derive `tenant_id` from authenticated, server-side identity/context—not request body, query parameters, headers supplied by clients, or LLM output.
- Every tenant-owned query, update, delete, cache key, task payload, vector-store operation, and audit record must be scoped by tenant.
- Make authorization checks explicit before reads and writes. Default deny.
- Never accept an object ID as proof of ownership. Verify both tenant scope and resource authorization.
- Prevent IDOR through tests that attempt cross-tenant reads, writes, deletes, exports, and background-job access.
- Include tenant scope in unique constraints and indexes where appropriate.
- Avoid putting tenant/customer data in shared caches; use namespaced keys and safe invalidation.
- Treat admin/support paths as privileged and auditable; do not bypass isolation for convenience.

## Database and migrations

- Use parameterized queries/ORM expressions; never concatenate user input into SQL.
- Use transactions for multi-step state transitions and define isolation/locking intentionally.
- Make migrations forward-safe, reviewable, and reversible where practical. Separate expand, backfill, and contract steps for large tables.
- Never silently delete or overwrite incident evidence. Soft-delete or append audit records when product semantics require retention.
- Test constraints, rollback/error paths, pagination, ordering, and tenant filters.

## LLM and zero-retention compliance

LLMs are untrusted probabilistic dependencies. They do not authorize actions and do not define schemas.

- Send only the minimum permitted data, with redaction/minimization before provider calls.
- Maintain zero-data-retention provider configuration and do not add fallback providers that violate the requirement.
- Use async Anthropic/Bedrock clients or isolate synchronous SDK calls with `asyncio.to_thread`.
- Validate every response with strict Pydantic V2 models; reject malformed, extra, ambiguous, or unsafe output according to the boundary contract.
- Treat model text as data, never executable code, SQL, shell, HTML, or authorization.
- Defend against prompt injection in logs, alerts, tickets, repositories, and tool output. Separate instructions from untrusted evidence.
- Bound tokens, input size, latency, retries, and cost. Record metadata only—never raw prompts/responses or customer content unless an approved, redacted audit design explicitly requires it.
- Keep deterministic policy checks outside the model. A model may recommend diagnosis or remediation; policy and human approval must decide execution.
- Test provider timeouts, rate limits, malformed JSON, refusal, partial output, prompt injection, and sensitive-data leakage.

## API and frontend contracts

- Preserve backward compatibility unless a versioned change is intentional.
- Validate request size, pagination, enum values, content types, and upload limits.
- Return stable, minimal error envelopes with correlation IDs; do not expose internals.
- Use consistent loading, empty, error, and retry states in the frontend.
- Type API responses from a shared/explicit contract; do not scatter unchecked casts.
- Escape/render untrusted incident text safely. Do not inject raw HTML.
- Never store tokens or sensitive incident data in localStorage unless an approved security design requires it.
- Keep accessibility, keyboard navigation, and visible failure states intact.

## Incident safety and observability

- Diagnosis must be evidence-backed: preserve source, timestamp, confidence, and correlation metadata without exposing sensitive content.
- Separate detection, investigation, recommendation, approval, execution, and verification states.
- Remediation actions require allowlists, dry-run support, idempotency, scoped credentials, audit records, and explicit human approval where required.
- Add correlation IDs and structured, redacted logs. Never log authorization headers, API keys, full prompts, customer payloads, or raw stack traces to user-visible systems.
- Metrics must be low-cardinality and avoid tenant/customer identifiers unless approved. Track latency, queue age, failures, retries, provider errors, and approval outcomes.
- Fail closed for authorization, tenant context, schema validation, and remediation policy checks. Fail safe for diagnosis availability where possible.

## Testing expectations

Every feature or fix should include the narrowest relevant tests plus regression coverage. Include:

- happy path and validation failures;
- authentication and authorization failures;
- cross-tenant isolation attempts;
- timeout, cancellation, retry, duplicate-delivery, and partial-failure behavior;
- malformed LLM output and prompt-injection fixtures;
- API contract and frontend loading/error states;
- migration/constraint behavior when persistence changes.

Use deterministic fixtures. Mock external providers and isolate network access. Tests must not call real Anthropic, Bedrock, customer systems, production databases, or production Redis.

## Dependency and configuration hygiene

- Do not add a dependency when the standard library or existing dependency is sufficient.
- Review licenses, maintenance, transitive risk, and async behavior before adding packages.
- Update lockfiles and dependency metadata together.
- Configuration comes from environment/secret management; `.env.example` documents names and safe placeholders only.
- Never commit secrets, certificates, private keys, tokens, dumps, generated customer data, or provider transcripts.

## Git and completion checklist

Before committing:

- `git diff --check` passes.
- No secrets or sensitive fixtures are present.
- Tenant scope and authorization are enforced on every affected path.
- No blocking calls exist in async paths.
- Pydantic schemas and API/frontend types agree.
- Focused and full tests pass, plus Ruff and frontend checks as applicable.
- Documentation/configuration reflects behavior.
- The commit is focused and the message explains intent.

In the final response, report what changed, files touched, checks run and their results, known limitations, and any follow-up needed. Do not claim a check passed unless it was actually run.
