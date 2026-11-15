# Contributing to TraceroAI

Thanks for helping. Bug reports, fixes, docs and new evaluators are all welcome. For
anything larger than a small fix, open an issue first so we can agree on the approach
before you spend time on it.

## Layout

| Path | What it is |
|---|---|
| `services/api` | FastAPI service, background worker, evaluators, migrations |
| `sdks/python` | The `traceroai` package on PyPI |
| `traceroai-web` | Next.js dashboard, docs and landing page |
| `infra/docker-compose.yml` | The whole stack for local development and self-hosting |
| `examples/` | Example apps using the SDK |

## Setting up

You need Python 3.11+ (CI uses 3.14), Node 22 and Docker.

```bash
# Postgres and Redis
docker compose -f infra/docker-compose.yml up -d postgres redis

# API
cd services/api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.lock -e ".[dev]"
python -m app.db.init_db
uvicorn app.main:app --reload

# SDK
cd sdks/python && pip install -e ".[recovery]" pytest

# Web
cd traceroai-web && npm install && npm run dev
```

Copy `.env.example` to `.env` at the repo root for local settings. Keep it pointed at
local services: the API reads it on startup, and anything in it (a hosted database, a
provider key) is what your local runs will use. To switch a service off for one run,
set its variable to an empty value, e.g. `TRACEROAI_OPENAI_API_KEY=`.

## Checks

CI runs all of these; running them first saves a round trip.

```bash
# API (from services/api)
ruff check .
pyright
pytest -q                     # uses the traceroai_test database on local Postgres

# SDK (from sdks/python)
pytest -q

# Web (from traceroai-web)
npx tsc --noEmit && npm run lint && npm run build
```

API tests refuse to run against a non-local database, and they never call an LLM
provider: the judge and embeddings are stubbed.

## Changing things

**Database.** Edit `services/api/app/db/models.py`, then generate and review a migration:

```bash
alembic revision --autogenerate -m "short description"
```

`alembic check` in CI-like setups should then report no differences.

**API dependencies.** Edit `services/api/requirements.txt`, then regenerate the lock
(CI fails if they disagree):

```bash
uv pip compile requirements.txt --universal --python-version 3.14 --generate-hashes -o requirements.lock
```

**Evaluators.** Diagnosis accuracy is measured on a labelled set. Run
`python -m app.eval.benchmark --no-provider` before and after a change; with a provider
key, run it without `--no-provider` too. See `docs/evaluation-benchmark.md`. If you
change a diagnosis rule, say how the numbers moved in the PR.

**Web.** `traceroai-web` uses a recent Next.js whose APIs differ from older releases;
check `node_modules/next/dist/docs` before using an API you haven't used here.

## Pull requests

- One change per PR, with tests for behaviour changes and bug fixes (a test that fails
  without the fix).
- Describe what changed and why, and how you checked it.
- User-facing changes get a line in `CHANGELOG.md` under "Unreleased".

## Releasing the SDK

Maintainers: bump `sdks/python/traceroai/_version.py`, move the "Unreleased" changelog
entries under the new version, merge, then push a tag `sdk-v<version>`. The release
workflow tests the package and publishes it to PyPI through trusted publishing.
