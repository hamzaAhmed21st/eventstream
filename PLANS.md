# EventStream MVP plan

## Product objective

Deliver a working, reviewable metrics-processing platform that demonstrates validated HTTP ingestion, asynchronous Redis Stream processing, idempotent PostgreSQL persistence, query APIs, and a React dashboard driven by real persisted data.

## MVP scope

The MVP accepts five metric types (`latency_ms`, `request_count`, `error_count`, `cpu_usage`, and `memory_usage`), publishes accepted events to Redis, persists them through a worker, exposes paginated events and aggregate summaries, displays those APIs in a polling dashboard, and includes deterministic synthetic traffic, tests, Compose, CI, and contributor documentation.

Authentication, alerts, rollups, streaming browser updates, retry/dead-letter policy, pending-message recovery, worker heartbeats, tracing, benchmarks, and deployment are explicitly deferred.

## Architecture and data flow

1. A client submits a versioned, timezone-aware metric event to FastAPI.
2. Pydantic normalizes and validates the event; the API publishes one JSON payload to a named Redis Stream and returns HTTP 202.
3. A worker performs blocking reads through a named consumer group.
4. The worker inserts the event in PostgreSQL in a transaction. A unique `event_id` makes a later replay of a pending entry safe to deduplicate.
5. Only a committed insert or confirmed duplicate is acknowledged in Redis.
6. Query endpoints read PostgreSQL for pagination and filtered aggregates.
7. The React dashboard polls readiness, summaries, and recent events and never invents values.

See `docs/architecture.md` for diagrams and failure boundaries.

## Milestones

1. Establish repository rules, plan, architecture, ignore policy, runtime pin, and contributor entry points.
2. Implement ingestion schemas, validation, health routes, and Redis publication.
3. Implement the consumer group worker, explicit acknowledgement, graceful shutdown, and structured logs.
4. Add the SQLAlchemy model, indexes, transaction handling, and verified initial Alembic migration.
5. Add paginated event and filtered summary APIs.
6. Build the responsive React/Vite dashboard with loading, empty, error, health, metric, filter, and recent-event states.
7. Add deterministic configurable synthetic traffic.
8. Integrate PostgreSQL, Redis, API, worker, and frontend in Docker Compose.
9. Add backend and frontend behavior tests, including real service-boundary integration where practical.
10. Add GitHub Actions and complete project, contributor, security, and GitHub template documentation.
11. Run the complete quality suite and verify the real event path end to end.
12. Create logical local commits and prepare a truthful review report without pushing.

## Principal risks and mitigations

- **Python 3.14 dependency support:** require Pydantic >=2.12, lock resolved versions, build images, and execute the full suite on CPython 3.14.6.
- **Acknowledgement before durability:** keep persistence and duplicate detection ahead of `XACK`; leave failed messages pending.
- **Duplicate delivery:** enforce `event_id` uniqueness in PostgreSQL and handle unique violations explicitly.
- **Startup races:** use service health checks, dependency conditions, and migrations before API readiness.
- **Unsafe tests:** isolate PostgreSQL and Redis test namespaces from development data.
- **Frontend contract drift:** share documented response shapes through strict TypeScript definitions and representative response tests.
- **Misleading readiness:** distinguish process liveness, dependency readiness, stream acceptance, and eventual database persistence.

## Definition of done

- CPython is pinned to 3.14.6 and dependencies resolve through uv and pnpm lockfiles.
- All specified routes, validation rules, stream behavior, model constraints, indexes, dashboard states, and generator controls exist.
- The initial migration upgrades a real PostgreSQL database successfully.
- Ruff, mypy, backend tests, TypeScript, frontend tests, frontend build, Docker image builds, and Compose validation pass.
- PostgreSQL, Redis, API, and frontend become healthy under Compose; the worker is running and log-clean.
- A real synthetic event appears in Redis, is persisted by the worker, is returned by query and summary APIs, and is rendered from the dashboard's real API requests.
- Documentation describes exact commands, verified capabilities, limitations, and roadmap without unsupported performance claims.
- Logical commits preserve the foundation, MVP implementation, and focused corrective history for review.

## Verification commands

```text
uv sync --locked
make lint
make typecheck
make test
pnpm --dir frontend build
docker compose config --quiet
docker compose build
docker compose up -d
make migrate
make seed
make verify
```

End-to-end verification additionally inspects the Redis stream/consumer state, PostgreSQL row, query APIs, summary API, and frontend-served dashboard/API requests.

## Deferred advanced features

- Sliding-window rollups and durable aggregate tables
- Configurable alert rules, transitions, cooldowns, and notification delivery
- Pending-entry recovery, bounded retries, dead-letter streams, and worker heartbeats
- API-key authentication and authorization
- WebSocket or Server-Sent Events updates
- Formal performance and load testing
- Distributed tracing and production telemetry
- Production orchestration and deployment
- AI or chat functionality
