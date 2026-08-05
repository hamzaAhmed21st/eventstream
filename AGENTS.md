# EventStream contributor guide

This file applies to the entire repository. EventStream is an MVP metrics pipeline whose verified path is client -> FastAPI -> Redis Stream -> worker -> PostgreSQL -> query API -> React dashboard.

## Repository layout

- `backend/app/api`: HTTP routers and dependency wiring.
- `backend/app/core`: configuration, logging, and shared runtime concerns.
- `backend/app/db`: SQLAlchemy engine, sessions, and declarative base.
- `backend/app/models`: persisted database models.
- `backend/app/schemas`: Pydantic request and response contracts.
- `backend/app/services`: Redis publication and database query services.
- `backend/app/workers`: Redis Stream consumer and persistence loop.
- `backend/migrations`: Alembic environment and revision history.
- `backend/tests`: backend unit and integration tests.
- `frontend/src`: React dashboard, API client, types, components, and tests.
- `scripts`: local synthetic traffic and verification helpers.
- `docs`: architecture and operational documentation.

## Approved development commands

Use the root `Makefile` as the public interface:

- `make setup`: install locked backend and frontend dependencies.
- `make up`: build and start the local Compose stack.
- `make down`: stop containers without deleting named volumes.
- `make logs`: follow Compose logs.
- `make migrate`: apply Alembic migrations to the configured database.
- `make test`, `make test-backend`, `make test-frontend`: run tests.
- `make lint`: run Ruff and frontend linting.
- `make typecheck`: run mypy and TypeScript checks.
- `make seed`: send finite synthetic traffic to the API.
- `make verify`: run the major non-destructive quality gates.

Direct equivalents documented in `README.md` are also acceptable. Never run destructive Git commands, delete Docker volumes, push, deploy, or modify credentials without explicit approval.

## Required verification

Run the narrowest relevant check while editing, then the broader suite before handoff. Backend work requires Ruff, mypy, and pytest. Frontend work requires TypeScript checking, Vitest, and a production build. Schema work also requires a successful Alembic upgrade against an isolated development or test PostgreSQL database. Cross-component changes require Docker Compose configuration validation and end-to-end verification with real Redis and PostgreSQL.

Never claim that a command, test, migration, build, health check, or data-flow step passed unless it was actually executed successfully. Record anything skipped or blocked.

## Coding conventions

- Target CPython 3.14.6 and current Python 3.14-compatible dependencies.
- Use typed Python, Pydantic v2 models, SQLAlchemy 2-style statements, explicit transactions, UTC-aware timestamps, and async I/O at network boundaries.
- Keep HTTP routers thin; place publication, persistence, and query logic in services.
- Use structured logs with stable event names and contextual fields. Never log secrets.
- Keep TypeScript strict. Prefer small accessible React components and TanStack Query for server state.
- Do not fabricate dashboard values. UI metrics must come from documented API responses.
- Add focused tests for behavior and failure paths; do not disable valid checks or add blanket ignores.

## Database and migration rules

- Every persisted schema change needs an Alembic revision reviewed alongside its model change.
- Migrations must have working upgrade and downgrade paths where safe.
- Preserve the database-level unique constraint on external `event_id` and useful query indexes.
- Test only against the isolated test database. Never truncate or drop a normal development database.
- A Redis message is acknowledged only after a committed insert or confirmation that its `event_id` already exists.

## API compatibility

- Version public routes beneath `/api/v1`.
- Treat accepted ingestion as Redis publication, not proof of PostgreSQL persistence.
- Preserve response field meanings and pagination semantics. Additive changes are preferred; document breaking changes before implementation.
- Validate safely bounded finite numbers, pagination, timezone-aware timestamps, schema versions, metric names, service normalization, and tag bounds at the API boundary.
- Keep readiness dependency-aware and liveness process-only.

## Documentation expectations

Update `README.md`, `PLANS.md`, and `docs/architecture.md` when commands, runtime behavior, architecture, limitations, or roadmap change. Do not publish invented benchmarks or describe deferred reliability features as complete.

## Git workflow

Work on a focused feature branch based on the current default branch. Keep commits logical and reviewable, verify the relevant milestone before committing, and inspect staged changes. Do not commit `.env`, tokens, credentials, virtual environments, dependency directories, database data, caches, coverage output, or generated builds. Do not push or open external GitHub artifacts without approval.

## Security rules

Use environment variables and safe local defaults; commit only `.env.example`. Validate all untrusted input, parameterize database operations through SQLAlchemy, constrain CORS, avoid leaking exception internals, and keep dependencies locked. Never change credentials or expose secrets in code, logs, fixtures, screenshots, or commit history.
