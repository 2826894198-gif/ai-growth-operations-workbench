# Deployment Runbook

**Who:** platform admin (GitHub Actions, environment-protected)
**Preflight:** CI green, `make production-check`, staging healthy

1. Promote exact staging image (immutable tag/digest, no rebuild).
2. Backup DB and verify restore point (`make backup-db-logical && make verify-backups`).
3. Run expand migration (`alembic upgrade head`).
4. Deploy backward-compatible app image.
5. Health gate: `/readyz`, `/api/v1/execution/health`, dashboard.
6. Record release (`POST /api/v1/releases`).
7. Post-deploy smoke (`make smoke-production-readonly`); no live mutation.
8. Observe metrics/alerting for 30 min.
