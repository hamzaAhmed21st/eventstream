# EventStream: implementation and verification

This guide connects the pipeline's claims to code, test assertions, and a recorded successful execution.

## Claim-to-code map

| Accomplishment | Implementation | Verification |
| --- | --- | --- |
| Asynchronous ingestion | [HTTP routes](../backend/app/api/routes/events.py), [Redis publisher](../backend/app/services/publisher.py), and [consumer-group worker](../backend/app/workers/main.py). | [Integration tests](../backend/tests/integration/test_pipeline.py), including `test_real_worker_loop_persists_idempotent_replay_and_serves_queries`. |
| Duplicate-safe persistence | [Database uniqueness and constraints](../backend/app/models/metric_event.py) and [transactional persistence](../backend/app/services/persistence.py). | `test_persistence_distinguishes_exact_replay_from_idempotency_conflict` checks matching replays and conflicting client fields. |
| Acknowledgment ordering | [Worker](../backend/app/workers/main.py): acknowledge after commit or duplicate/conflict verification; leave failed persistence pending. | [Worker tests](../backend/tests/test_worker.py) check inserted, duplicate, conflict, persistence-error, and acknowledgment-error outcomes. |
| Failure-path handling | Worker retains pending messages after persistence exceptions. | `test_worker_loop_leaves_failed_persistence_pending` uses real Redis with an injected failing persister. This is a simulated database exception, not a database-outage recovery test. |
| Safe schema changes | [Contract migration](../backend/migrations/versions/20260809_0002_enforce_metric_contract.py). | `test_contract_migration_preserves_invalid_legacy_rows_until_remediated` checks that an upgrade rejects invalid legacy data without silently deleting it, then succeeds after correction. |
| Dashboard backed by query APIs | [Query service](../backend/app/services/queries.py), [API client](../frontend/src/api/client.ts), and [dashboard](../frontend/src/pages/DashboardPage.tsx). | [React tests](../frontend/src/tests/App.test.tsx) use mocked HTTP responses; Compose separately checks live API responses through the frontend proxy. |

Test names in the table are in [the integration suite](../backend/tests/integration/test_pipeline.py) unless linked otherwise.

## Recorded CI evidence

[Successful run 31624110911](https://github.com/hamzaAhmed21st/eventstream/actions/runs/31624110911), commit `eec8bbe8a749d45aa36122a1901e5d0059402f85`:

- Backend: **110 passed**.
- Frontend: **6 passed**.
- Migration verification, lint/type checks, frontend production build, and containerized smoke test succeeded.

The [Compose smoke test](../.github/workflows/ci.yml) runs actual API, Redis, worker, PostgreSQL, and frontend containers. Its recorded assertions confirm:

1. HTTP ingestion accepts an event and returns a stream ID.
2. The event becomes queryable; the persisted row and summary match the submitted payload.
3. The Redis entry is consumed and acknowledged.
4. An identical replay creates another stream entry but leaves **one PostgreSQL row**.
5. The frontend nginx proxy returns the real event and summary API responses.

This proves the exercised ingestion-to-query path through the frontend proxy. It is **not a browser-driven end-to-end rendering test**, a throughput benchmark, or a production availability guarantee. Counts refer to the linked historical run; the README badge links to current CI.

## Important design decisions

- A stable client-generated `event_id` identifies a logical event; a Redis stream ID identifies one delivery.
- Database uniqueness is the final duplicate guard. Transactions protect the write.
- An exact replay and a conflicting reuse of an event ID are different outcomes. Conflicts preserve the original row, are logged, and are acknowledged.
- HTTP 202 means Redis accepted the event. A conflict detected later by the worker is not returned synchronously to the HTTP client.
- A database exception leaves the message pending. The current worker does **not** automatically reclaim or retry pending messages.

## Try the evidence locally

Follow the [quick start](../README.md#quick-start), then the [five-minute demo](../README.md#five-minute-local-demo). Submit the same event twice and inspect the stream, consumer group, stored row, and query response.

`make verify` runs the repository's quality gates. Integration tests target isolated test resources, as described in the [test instructions](../README.md#tests-and-ci).

## Current boundaries

Automatic pending-message recovery, bounded retries, dead-letter handling, authentication, distributed tracing, and formal load benchmarks are not implemented. The dashboard polls; it does not use WebSockets. See the [roadmap](../ROADMAP.md) for future work.

[Back to the project](../README.md)
