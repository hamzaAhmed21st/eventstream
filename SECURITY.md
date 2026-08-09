# EventStream security policy

## Local-development boundary

EventStream is a local-development MVP, not an internet-facing service. Docker Compose binds
PostgreSQL, Redis, the API, and frontend ports to `127.0.0.1`; `.env.example` contains intentionally
simple local credentials. Keep CORS origins narrow and use the stack only on a trusted machine.

The current application does not provide authentication, authorization, tenant isolation, TLS
between services, or rate limiting. Do not expose the local defaults to an untrusted network.

## Report a vulnerability

This repository does not currently have a private vulnerability-reporting channel configured.
Never publish secrets, exploit details, or a security-sensitive reproduction in an issue, log,
screenshot, pull request, or discussion.

If a defect can be reported safely without sensitive details, credentials, or actionable exploit
information, use the [bug report form](.github/ISSUE_TEMPLATE/bug_report.yml). Otherwise, do not
post the report publicly; wait until the repository provides a private reporting channel.

For a safe report, include the affected revision, component, impact, minimal reproduction, and
suggested mitigation when available. Remove credentials and unrelated event data. No response-time
guarantee is made.

## Protect local data

- Never add `.env`, passwords, tokens, private keys, database files, or captured sensitive events
  to the repository.
- Treat application logs, command output, fixtures, screenshots, and shell history as possible
  disclosure paths.
- Keep database operations parameterized and validate every client-controlled event field.
- Keep structured failure logs to safe identifiers and error categories; do not log credentials or
  raw connection strings.
- Rotate an exposed credential immediately; removing it from a later revision is insufficient.

Only `.env.example` contains shareable example values. Runtime secrets belong in environment
variables or an appropriate external secret store.
