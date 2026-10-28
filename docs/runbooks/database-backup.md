# Database Backup Runbook

```bash
make backup-db-logical    # pg_dump -Fc, daily
make backup-db-base       # pg_basebackup, hourly window
make verify-backups       # pg_restore --list
make restore-drill        # restore to throwaway DB + count alembic_version
```

Encrypt backups, store off-host, and keep them out of the normal app archive.
P1 if no successful backup within 24h; P2 if restore drill overdue (>30d).
