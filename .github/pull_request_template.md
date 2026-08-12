## Summary

Describe the problem and the smallest useful solution.

## Verification

List the exact commands that ran and their results. Explain anything not run.

- [ ] `make lint`
- [ ] `make typecheck`
- [ ] `make test`
- [ ] `pnpm --dir frontend build`
- [ ] `docker compose config --quiet`

## Compatibility and safety

- [ ] API or schema changes are documented and tested; schema changes include an Alembic migration.
- [ ] HTTP `202` is treated as Redis publication, not PostgreSQL persistence.
- [ ] Worker acknowledgement or dashboard data-flow changes preserve the documented architecture.
- [ ] Tests use isolated services, and no secrets, local data, dependencies, or builds are included.
