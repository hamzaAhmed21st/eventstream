# Contributing to EventStream

EventStream favors small, verifiable changes that preserve the real pipeline from API acceptance
through Redis and PostgreSQL to the dashboard.

## Prepare the repository

Prerequisites and version requirements are listed in `README.md`. From the repository root:

```bash
cp .env.example .env
make setup
docker compose up -d postgres redis
make migrate
```

Run application processes locally in separate terminals when needed:

```bash
uv run uvicorn app.main:app --app-dir backend --reload
PYTHONPATH=backend uv run python -m app.workers.main
pnpm --dir frontend dev
```

The full five-service path starts with `docker compose up --build`.

The Vite development server binds to loopback by default. Only on a trusted network, opt into LAN
access explicitly with `pnpm --dir frontend dev --host 0.0.0.0`; doing so also exposes its API
proxy. Root `.env` is loaded by Compose and directly run Python processes, but Make does not
import it. Pass test URL overrides as environment variables or Make command-line variables.

## Development workflow

1. Start from an up-to-date branch and inspect `git status` before editing.
2. Make one focused behavior change, including tests and documentation.
3. Run the narrowest relevant checks while iterating.
4. Run the broader non-destructive suite before requesting review.
5. Review staged files for secrets, generated artifacts, and unrelated changes.
6. Use a concise commit subject that explains the behavior delivered.

Do not disable valid tests, add blanket lint/type ignores, invent verification results, or commit
`.env`, credentials, dependency directories, database data, caches, coverage, or generated builds.

## Quality checks

Backend changes require:

```bash
uv run ruff check backend scripts
uv run mypy backend scripts
uv run pytest
```

The stable `make test-backend` target is preferred for the complete suite: it prepares the
isolated `eventstream_test` database and Redis database 15 before pytest. A direct `uv run pytest`
executes integration tests only when `TEST_DATABASE_URL` and `TEST_REDIS_URL` are set; otherwise
those guarded tests are reported as skipped.

Frontend changes require:

```bash
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build
```

Cross-component work also requires:

```bash
docker compose config --quiet
docker compose build
docker compose up -d
```

Then verify a real event at the Redis, worker, PostgreSQL, query API, and dashboard boundaries as
described in `README.md`. Report every relevant command actually run and any skipped or failed
check; never infer a pass from code inspection.

## Backend and API changes

- Keep public HTTP routes under `/api/v1`; prefer additive compatibility.
- Keep routers thin and typed. Put publication, persistence, and query behavior in services.
- Treat HTTP 202 as confirmed Redis publication only, not PostgreSQL durability.
- Validate untrusted values at the API boundary and preserve timezone-aware UTC timestamps.
- A worker may acknowledge only after a committed insert or a confirmed duplicate `event_id`.
- Use structured logs with stable event names and no secrets or raw credentials.
- Add failure-path tests as well as successful-path tests.

Document any breaking field, pagination, filter, status-code, or semantic change before proposing
it. Update representative frontend response tests with API contract changes.

## Database migrations

Every persisted schema change needs a matching Alembic revision. Generate and inspect it rather
than trusting autogeneration blindly:

```bash
uv run alembic revision --autogenerate -m "describe the schema change"
uv run alembic upgrade head
```

Provide a safe downgrade where practical. Preserve database-level `event_id` uniqueness and
query indexes, use SQLAlchemy 2-style statements and explicit transactions, and verify the
migration against an isolated development/test PostgreSQL database. Never drop or truncate a
normal development database to make a test pass.

## Frontend changes

- Keep TypeScript strict and model the backend response shapes explicitly.
- Use TanStack Query for remote state and do not fabricate fallback metrics.
- Preserve accessible labels, semantic controls, keyboard behavior, and responsive layouts.
- Exercise loading, empty, error, success, and filter states in tests.
- The production frontend uses same-origin `/api` and `/health` paths through nginx.

## Documentation and pull requests

Update the README, architecture guide, plan, and operational instructions whenever behavior,
commands, failure boundaries, or known limitations change. Do not publish synthetic traffic as a
benchmark.

Pull requests should explain the problem and behavior, list exact verification evidence, call out
migrations or compatibility implications, and include screenshots for material UI changes. Keep
commits logical; do not create empty commits or force-push shared review history without explicit
coordination.
