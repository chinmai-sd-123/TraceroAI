# Plans & Limits

## Plans

We offer three plans: Free, Pro, and Enterprise.

The **Free** plan includes 1 project, community support, and is intended for evaluation
and small personal use. It has no SLA and features may change without notice.

The **Pro** plan adds unlimited projects, email support with a one-business-day response
target, and access to the full evaluation suite. Pro is billed per seat, monthly or
annually, and annual billing carries roughly a two-month discount versus monthly.

The **Enterprise** plan adds single sign-on (SSO via SAML or OIDC), audit logs with
configurable retention, a dedicated customer success manager, a 99.9% uptime SLA, and
the option of a private deployment region. Enterprise pricing is custom and negotiated
per organization based on seat count and data-residency requirements.

## Usage Limits

The maximum file upload size is 100 megabytes per file. This applies uniformly across
plans; larger files must be split or uploaded via the resumable upload API.

API rate limits depend on the plan. Free accounts are limited to 1,000 API requests per
day. Pro accounts are limited to 100,000 requests per day. Enterprise limits are set by
contract and can be raised on request. Exceeding the limit returns HTTP 429 with a
Retry-After header; sustained overage on Pro may be billed as usage overage rather than
hard-blocked.

## Storage and Retention

Free accounts retain trace data for 7 days. Pro retains 30 days. Enterprise retention is
configurable up to 400 days. Deleted data is purged from backups within 35 days.
