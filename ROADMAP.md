# EventStream roadmap

These are concrete next steps beyond the current local MVP; none is implemented yet.

- Reclaim abandoned consumer-group entries with `XAUTOCLAIM` and explicit ownership rules.
- Add bounded retries with backoff and a dead-letter stream for exhausted messages.
- Trim the Redis Stream without discarding entries that are still pending.
- Report worker heartbeat, consumer lag, oldest pending age, and persistence outcomes.
- Replace deep offset pagination with a stable event-time and row-identity cursor.
- Add snapshot-aware reads where event lists and summaries need one consistent view.
- Introduce retention-aware rollup tables while preserving each metric's unit.
- Generate frontend contracts from OpenAPI or validate responses at runtime.
- Add authentication and rate limits before operating outside trusted localhost use.
- Evaluate SSE or WebSockets if the dashboard needs push updates instead of polling.
- Publish reproducible latency and throughput benchmarks before making performance claims.
