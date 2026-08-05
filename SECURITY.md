# EventStream security policy

## Supported code

EventStream is an early local-development MVP. Security fixes target the current default branch
and active review branches; old commits and forks are not maintained releases.

The Compose configuration and `.env.example` contain intentionally simple localhost defaults.
They are not suitable for an internet-facing or production environment.

## Report a vulnerability

Do not open a public issue for a suspected vulnerability or include exploit details in ordinary
logs, screenshots, pull requests, or discussions. Use the repository's **Security** tab and
private vulnerability reporting:

<https://github.com/hamzaAhmed21st/eventstream/security/advisories/new>

Include the affected commit, component, impact, minimal reproduction, and any suggested
mitigation. Remove tokens, credentials, and unrelated user or event data. Maintainers will
coordinate disclosure after the report can be reproduced and a remediation is understood; this
document does not promise a fixed response timeline.

For ordinary defects without security impact, use the bug report form.

## Secrets and sensitive data

- Never commit `.env`, passwords, tokens, private keys, production connection strings, database
  files, or captured production events.
- Store runtime values in environment variables or an appropriate external secret manager.
- Treat logs, CI output, fixtures, screenshots, and shell history as possible disclosure paths.
- Keep structured failure logs to sanitized categories and safe identifiers. SQL statement
  parameters and complete validation errors must not be emitted.
- Rotate a credential immediately if it is exposed; removing it in a later commit is insufficient.
- Keep database operations parameterized through SQLAlchemy and validate all client-controlled
  event fields.

Only `.env.example` belongs in version control, and its values must remain non-sensitive local
examples.

## MVP threat boundaries

The current MVP demonstrates a local metrics pipeline, not a hardened hosted service. It does not
yet provide API-key authentication, authorization, tenant isolation, rate limiting, encrypted
service-to-service transport, automated secret rotation, or production network policy. Redis and
PostgreSQL are bound to loopback by Compose, and the API's CORS origins should remain narrowly
configured.

Before any deployment, perform a dedicated threat model and dependency/container scan; provision
unique secrets; enable TLS, authentication, authorization, least-privilege database roles,
backups, retention, audit logging, network controls, and operational monitoring. Do not infer
production readiness from passing local tests.

## Dependency handling

Python and JavaScript dependencies are locked and should be updated in focused, reviewed changes.
CI must continue to fail on required lint, type, test, migration, or build errors. Do not suppress
a security-related failure with a blanket ignore or silently downgrade Python to bypass package
compatibility.
