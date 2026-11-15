# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue: use **Report a
vulnerability** on the repository's Security tab (GitHub private vulnerability
reporting). Include what you found, how to reproduce it, and the impact you expect.

We aim to acknowledge reports within a week and to keep you updated until a fix is
released. Once it is, we're happy to credit you in the release notes if you'd like.

## Supported versions

Fixes go into the latest release of the API, dashboard and `traceroai` SDK. Upgrade to
the latest version before reporting, if you can.

## Scope

In scope: the API (`services/api`), the worker, the dashboard (`traceroai-web`) and the
SDK (`sdks/python`): for example, reading another project's data, bypassing API key
checks, injection, or a way to make the server run code.

Out of scope: the public demo's rate limits and data, findings that need a stolen admin
key or server access, and vulnerabilities in third-party dependencies that already have
a published fix (Dependabot raises those).

## Running TraceroAI safely

- Set `TRACEROAI_APP_ENV=production`, so API keys are required.
- Give the dashboard an admin key only together with `TRACEROAI_DASHBOARD_PASSWORD`, or
  keep it on a private network.
- Traces contain your users' questions and your documents. Set
  `TRACEROAI_TRACE_RETENTION_DAYS`, and keep the database private. See
  [What a trace contains](docs/trace-data.md) for every field stored and where it can go.
- Leave `TRACEROAI_PLAYGROUND_ENABLED` off unless you want a public demo.
