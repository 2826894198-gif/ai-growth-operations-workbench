# Local bootstrap and safe operating baseline

This is the supported path for first-time local use. It starts the application
with mock providers, shadow rules, and every provider write switch disabled.

## Prerequisites

- Docker Desktop running
- Python 3.12 and `uv`
- Node.js 22 and npm

The repository-local virtual environments and `node_modules` can be rebuilt with:

```bash
make bootstrap
```

## Start and seed the full stack

```bash
make up-safe
make seed-safe
make verify-local
```

Open <http://127.0.0.1:15173>. The API readiness endpoint is
<http://127.0.0.1:8000/readyz>.

Port `15173` avoids collisions with other Vite projects. Override it when needed
with `make up-safe DASHBOARD_PORT=15174`.

The Compose stack reads `config/env/local.env.example` by default. To use a
private environment file, keep it outside Git and run:

```bash
ENV_FILE=/absolute/path/to/private.env make up-safe
```

## Safety boundary

The checked-in local, staging, and production templates intentionally default to:

```text
DATA_PROVIDER_MODE=mock
SOCIAL_PROVIDER_MODE=mock
AI_PROVIDER_MODE=mock
EXECUTION_ENABLED=false
META_WRITE_ENABLED=false
GOOGLE_ADS_WRITE_ENABLED=false
ALLOW_LIVE_EXECUTION_TESTS=false
```

Do not enable live provider modes until read credentials, account scopes, data
reconciliation, and alerting have been verified. Enabling read access does not
authorize write access. Provider write switches should be enabled one provider
at a time only after a separate deployment approval.

## Verification before a pull request

```bash
make lint
make test-all
cd frontend && npm audit --audit-level=high && npm run build
docker compose -f compose.yaml -f compose.dev.yaml config --quiet
```

## Stop without deleting data

```bash
make down
```

This preserves the PostgreSQL and Redis named volumes. Removing volumes is a
separate destructive operation and is not part of the normal workflow.
