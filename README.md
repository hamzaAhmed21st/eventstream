# EventStream

EventStream is a small end-to-end metrics platform built to demonstrate validated HTTP
ingestion, asynchronous Redis Stream processing, idempotent PostgreSQL persistence, and a
React dashboard backed by real query results.

Current status: the first MVP implementation is prepared for review. Its review gate is the
verification sequence in this document: a capability should not be treated as verified merely
because its code or configuration exists.

## How it works

```mermaid
flowchart LR
    C[Synthetic or HTTP client] -->|POST /api/v1/events| A[FastAPI]
    A -->|XADD| R[(Redis Stream)]
    R -->|XREADGROUP| W[Worker]
    W -->|transactional insert| P[(PostgreSQL)]
    W -->|XACK after commit or duplicate| R
    P -->|events and summary queries| A
    A -->|real JSON responses| D[React dashboard]
```

The ingestion API returns HTTP `202 Accepted` only after the running Redis instance accepts the
event. A 202 means “accepted into the stream,” not “stored in PostgreSQL” or synchronously
replicated with a zero-loss guarantee. Local Redis uses AOF with `appendfsync everysec`, so an
abrupt host failure can still lose a recently accepted entry. The worker acknowledges a stream
message only after its database transaction commits or the external `event_id` is safely
confirmed as a duplicate.

The MVP includes:

- versioned validation for latency, request, error, CPU, and memory metrics;
- process liveness and dependency-aware readiness endpoints;
- a named Redis Stream, consumer group, blocking worker, explicit acknowledgement, and
  database-level duplicate protection;
- paginated event queries and filtered summary statistics;
- a polling dashboard with readiness, loading, empty, error, filter, metric, and recent-event
  states;
- deterministic, rate-controlled synthetic traffic;
- Alembic migrations, backend and frontend tests, Docker Compose, and GitHub Actions CI.

See [the architecture guide](docs/architecture.md) for component ownership, the complete event
sequence, and failure boundaries.

## Technology stack

- Python 3.14.6, uv, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg 3, and redis-py
- PostgreSQL 17 and Redis 7.4 Streams
- React, TypeScript, Vite, TanStack Query, Recharts, Vitest, and Testing Library
- Ruff, mypy, pytest, pnpm, Docker Compose, and GitHub Actions

Pydantic is constrained to a Python 3.14-compatible release (`>=2.12`). If dependency resolution
fails on Python 3.14, capture and diagnose the exact error rather than silently changing Python.

## Prerequisites

- Python 3.14.6 available to uv; `.python-version` contains the exact patch version
- uv
- Node.js 22 or newer and pnpm 10 or newer
- Docker Desktop with Docker Compose
- `make`

## Setup and startup

Create a local configuration file and install project-local dependencies:

```bash
cp .env.example .env
make setup
```

The values in `.env.example` are local-development defaults, not production credentials. If you
change the PostgreSQL username, password, or database, update `DATABASE_URL` to match. Docker
Compose automatically reads root `.env` values used in `docker-compose.yml`; Python processes
started from the repository root also load `.env`. Make does not import `.env`, so pass test URL
overrides in the shell or as Make variables.

Build and run PostgreSQL, Redis, the API, worker, and frontend:

```bash
docker compose up --build
```

The API container applies `alembic upgrade head` after PostgreSQL and Redis become healthy, then
starts Uvicorn. The worker and frontend wait for API readiness. PostgreSQL, Redis, API, and
frontend have Compose health checks; the worker is verified by its running state and structured
logs. Stop the stack without deleting its named volumes:

```bash
make down
```

Do not add `--volumes` unless deliberately resetting local data and authorized to do so.

## Local URLs

| Resource | URL |
| --- | --- |
| Dashboard | <http://localhost:5173> |
| OpenAPI/Swagger UI | <http://localhost:8000/docs> |
| OpenAPI JSON | <http://localhost:8000/openapi.json> |
| Liveness | <http://localhost:8000/health/live> |
| Readiness | <http://localhost:8000/health/ready> |

Compose publishes service ports on `127.0.0.1`. Containers use the internal service names
`postgres`, `redis`, and `api`; they do not use `localhost` to reach one another.

## Database migrations

Compose applies migrations during API startup. To apply them explicitly from the host while the
database is running:

```bash
make migrate
```

Or run the same operation inside the API container:

```bash
docker compose exec api uv run alembic upgrade head
```

Migration success must be established against a real development or isolated test PostgreSQL
database; generating a revision alone is not verification.

## Development commands

| Command | Purpose |
| --- | --- |
| `make setup` | Resolve/install backend and locked frontend dependencies |
| `make up` | Run `docker compose up --build` |
| `make down` | Stop services without deleting volumes |
| `make logs` | Follow recent Compose logs |
| `make migrate` | Upgrade the database to the latest Alembic revision |
| `make test` | Run backend and frontend test suites |
| `make test-backend` | Prepare isolated PostgreSQL/Redis resources and run all pytest tests |
| `make test-frontend` | Run Vitest |
| `make lint` | Run Ruff and ESLint |
| `make typecheck` | Run mypy and TypeScript checks |
| `make seed` | Submit 100 deterministic synthetic events |
| `make verify` | Run lint, types, tests, frontend build, and Compose validation |

Major non-destructive checks can also be run directly:

```bash
uv sync --locked
uv lock --check
uv run ruff check backend scripts
uv run mypy backend scripts
uv run pytest
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build
docker compose config --quiet
```

Tests that mutate PostgreSQL or Redis must target isolated test resources, never ordinary
development data.

`make test-backend` starts the Compose PostgreSQL and Redis services, creates the separate
`eventstream_test` database if needed, applies Alembic to that database, and supplies Redis
database 15 to the integration tests. Override `TEST_DATABASE_URL` or `TEST_REDIS_URL` when the
safe local defaults do not match your environment:

```bash
make test-backend \
  TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/eventstream_test \
  TEST_REDIS_URL=redis://localhost:6379/15
```

Make suppresses these credential-bearing command expansions. For a unit-only iteration without
Docker, run `uv run pytest -m 'not integration'` explicitly.

The Vite development server binds to `127.0.0.1` by default. A developer who deliberately needs
LAN access can opt in with `pnpm --dir frontend dev --host 0.0.0.0`; this also exposes the local
API proxy and should be used only on a trusted network.

## Send synthetic events

With the stack running, submit a finite deterministic sample:

```bash
make seed
```

Customize the count, rate, services, and seed through Make variables:

```bash
make seed SEED_COUNT=500 SEED_RATE=20 SEED_SERVICES=checkout,catalog SEED_RANDOM=7
```

Or invoke the generator directly. Omitting `--count` runs until `SIGINT` or `SIGTERM`; Ctrl-C
stops cleanly and prints accepted and failed request counts.

```bash
uv run python scripts/generate_events.py \
  --api-url http://localhost:8000 \
  --events-per-second 10 \
  --count 100 \
  --services checkout,catalog,accounts \
  --seed 42
```

This traffic includes occasional latency/CPU spikes and error events. It is test data, not a
benchmark, and the project makes no throughput or latency claims from it.

## HTTP API

Submit one event:

```bash
curl --fail-with-body -X POST http://localhost:8000/api/v1/events \
  -H 'Content-Type: application/json' \
  -d '{
    "service": "checkout",
    "metric_name": "latency_ms",
    "value": 84.2,
    "timestamp": "2026-08-05T18:00:00Z",
    "tags": {"environment": "local"},
    "schema_version": 1
  }'
```

Public endpoints are:

- `POST /api/v1/events` — validate and publish an event, returning 202 after `XADD`;
- `GET /api/v1/events` — list persisted events with pages from 1 through 1,000,000 and page sizes
  from 1 through 100;
- `GET /api/v1/metrics/summary` — return count, min, max, average, and most recent data with
  required `metric_name` plus optional service, start, and end filters;
- `GET /health/live` — report whether the API process is alive;
- `GET /health/ready` — verify PostgreSQL and Redis connectivity.

Use the Swagger UI for the authoritative request, query, and response schemas.

Metric values must be finite and between `-1,000,000,000,000` and
`1,000,000,000,000`, inclusive. This is a shared ingestion safety bound that prevents unsafe
database aggregation; it does not define metric-specific business semantics.

## End-to-end verification

After the stack is healthy, send at least one real event and inspect each boundary:

```bash
curl --fail http://localhost:8000/health/ready
uv run python scripts/generate_events.py --count 1 --events-per-second 1 --seed 42
docker compose exec -T redis redis-cli XLEN eventstream:events
docker compose exec -T postgres psql -U eventstream -d eventstream \
  -c 'SELECT event_id, service, metric_name, value FROM metric_events ORDER BY id DESC LIMIT 1;'
curl --fail 'http://localhost:8000/api/v1/events?page=1&page_size=10'
curl --fail 'http://localhost:8000/api/v1/metrics/summary?service=checkout&metric_name=latency_ms'
```

Finally open the dashboard and verify in browser developer tools that its readiness, events, and
summary requests return the persisted data. Do not claim the end-to-end path passed unless Redis,
the worker, PostgreSQL, both query APIs, and the rendered UI were all checked successfully.

## Repository layout

```text
backend/             FastAPI application, worker, migrations, and tests
frontend/            React/Vite dashboard and tests
scripts/             Synthetic event generator
docs/                Architecture documentation
.github/              CI, pull-request template, and issue forms
docker-compose.yml   Local five-service runtime
Makefile             Stable development command interface
```

Contributor workflow and migration/API compatibility rules are in [CONTRIBUTING.md](CONTRIBUTING.md)
and [AGENTS.md](AGENTS.md). Security reporting is documented in [SECURITY.md](SECURITY.md).

## Known MVP limitations

- Redis pending entries are not automatically reclaimed after a worker failure.
- A crash after database commit but before acknowledgement can leave a pending entry. Its stable
  `event_id` makes later manual or future recovery safe to deduplicate, but the current worker
  does not automatically redeliver it.
- Redis AOF improves local restart recovery but does not provide synchronous replication or a
  zero-loss acceptance guarantee.
- There are no bounded retry policy, dead-letter stream, or worker heartbeats.
- Summaries scan raw events; rollups, retention management, and sliding windows are absent.
- The dashboard polls; WebSockets and Server-Sent Events are deferred.
- Local defaults have no API-key authentication or tenant isolation.
- There is no formal benchmark suite, distributed tracing, or production deployment.

## Roadmap

The next reliability increment is pending-entry recovery with delivery counters, bounded
exponential retry, and a dead-letter stream. Later work can add worker heartbeats, rollups and
retention, configurable alert state machines, authentication, streaming UI updates, tracing, and
production deployment. AI/chat functionality is not part of the current roadmap milestone.
