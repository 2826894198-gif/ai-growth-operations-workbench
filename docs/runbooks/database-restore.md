# Database Restore Runbook

1. Confirm restore point (backup file / PITR timestamp) and DB name.
2. Production requires explicit typed confirmation (`scripts/restore.sh`).
3. Restore to throwaway DB first and validate alembic head + row counts.
4. Point app to restored DB after verification.
5. Reconcile queues (`job_runs`), then re-run readiness + execution health.
