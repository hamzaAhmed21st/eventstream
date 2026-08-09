## Summary

Describe the problem and the smallest useful solution.

## Verification

List the exact commands that ran and their results. Mark checks that do not apply and
explain why.

- [ ] `make lint`
- [ ] `make typecheck`
- [ ] `make test`
- [ ] `pnpm --dir frontend build`
- [ ] `docker compose config --quiet`
- [ ] Relevant migration and end-to-end checks completed

## Data-flow and compatibility review

- [ ] HTTP 202 is described only as successful Redis publication, not database persistence.
- [ ] API response or pagination changes are documented and tested.
- [ ] Schema changes include a reviewed Alembic migration.
- [ ] Redis messages are acknowledged only after commit, confirmed exact duplication, or an
      explicitly classified permanent identifier conflict.
- [ ] Dashboard values come from real API response shapes.

## Safety and documentation

- [ ] No secrets, `.env`, dependency directories, database data, or build artifacts are included.
- [ ] Tests use isolated PostgreSQL and Redis resources.
- [ ] Documentation and known limitations are updated where needed.
- [ ] Screenshots are attached for material UI changes.
