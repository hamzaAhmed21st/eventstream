# EventStream roadmap

This roadmap describes future engineering work beyond the current local MVP. It does not imply
that any item below is implemented.

## Stream reliability and retention

- Reclaim abandoned pending entries with `XAUTOCLAIM` and explicit ownership rules.
- Track delivery attempts, apply bounded exponential backoff, and route exhausted or permanently
  invalid messages to a dead-letter stream with replay and inspection tooling.
- Coordinate Redis Stream trimming and data retention with pending-entry recovery so cleanup
  cannot silently strand work.
- Define graceful draining and recovery behavior for scaled worker instances.

## Query correctness and scale

- Add snapshot-consistent reads for event lists and summaries where a stable analytical view is
  required.
- Replace deep offset pagination with a stable cursor based on event timestamp and row identity.
- Introduce retention-aware rollups or aggregate tables without changing metric units or
  fabricating historical precision.

## Operability

- Expose worker and end-to-end pipeline health, including consumer lag, oldest pending age,
  processing outcomes, and last successful persistence.
- Establish a generalized exception policy that classifies transient, permanent, malformed, and
  unexpected failures consistently across API, worker, and scheduled operations.
- Add structured tracing across HTTP publication, Redis delivery, persistence, and queries.
- Build reproducible latency, throughput, recovery, and resource benchmarks with published test
  conditions.

## Contract management

- Generate frontend types from the OpenAPI schema or enforce equivalent runtime response
  validation to reduce drift between backend and browser contracts.
- Version future event and query changes with explicit compatibility and migration rules.

## Security and delivery

- Add authentication, authorization, tenant boundaries, rate limits, TLS, external secret
  management, least-privilege roles, and production network policy.
- Add dependency provenance, vulnerability scanning, image signing, SBOM generation, pinned base
  image digests, and container hardening.
- Define backup, restore, observability, environment promotion, and deployment procedures before
  operating the service outside local development.
