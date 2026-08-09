# Contributing to EventStream

Keep changes focused and preserve the real path from HTTP acceptance through Redis and
PostgreSQL to the dashboard. Prerequisites and service URLs are in [README.md](README.md).

## Local setup

```bash
cp .env.example .env
make setup
docker compose up -d --wait postgres redis
make migrate
```

Run individual processes when a focused feedback loop is useful:

```bash
uv run uvicorn app.main:app --app-dir backend --reload
PYTHONPATH=backend uv run python -m app.workers.main
pnpm --dir frontend dev
```

The full five-service stack starts with `docker compose up --build`. Local defaults bind service
ports to loopback. Make does not load `.env`; pass test URL overrides as Make variables or export
them in the shell.

## Verification

Use the narrowest relevant check while iterating, then run the broader gate:

```bash
make lint
make typecheck
make test
make frontend-build
make compose-config
```

`make verify` combines those checks. Backend work requires Ruff, mypy, and pytest. Frontend work
requires ESLint, TypeScript checking, Vitest, and a production build. Cross-component work also
requires a successful Compose build and a real API → Redis → worker → PostgreSQL → query API →
dashboard exercise.

`make test-backend` prepares the isolated `eventstream_test` PostgreSQL database, applies
migrations there, and uses Redis database 15. Override `TEST_DATABASE_URL` and `TEST_REDIS_URL`
when those safe local defaults do not match the machine. Never point mutating tests at normal
development data.

## Database changes

Every persisted schema change requires an Alembic revision with an inspected upgrade and a safe
downgrade where practical:

```bash
uv run alembic revision --autogenerate -m "describe the schema change"
uv run alembic upgrade head
```

Verify migrations against real isolated PostgreSQL. Preserve database-level `event_id`
uniqueness, metric-contract constraints, and useful query indexes. Do not drop or truncate a
normal development database to make verification pass.

## API compatibility

- Keep public routes under `/api/v1` and prefer additive changes.
- Treat `202 Accepted` as confirmed Redis publication, not PostgreSQL persistence.
- Require a stable client `event_id`; exact retries reuse both identifier and complete payload.
- Acknowledge only after a committed insert, confirmed exact replay, or explicitly classified
  permanent identifier conflict.
- Preserve field meanings, metric units, pagination behavior, timezone rules, and schema version.
- Keep routers thin, network boundaries async, SQL parameterized, and structured logs free of
  secrets.
- Update strict frontend response types and representative tests with API contract changes.

Do not disable valid checks, add blanket ignores, fabricate UI values, or include `.env`,
credentials, dependency directories, database files, caches, coverage output, or generated builds.
Architecture details are in [docs/architecture.md](docs/architecture.md), and security reporting
is in [SECURITY.md](SECURITY.md).
