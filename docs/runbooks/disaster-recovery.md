# Disaster Recovery Runbook

| Loss | System behavior | Recovery |
|---|---|---|
| Full host | Downtime | Restore Postgres backup, rebuild compose, reconnect browser node |
| Redis | Cache/queue loss | Rebuild lazily; requeue from DB (`job_runs`, execution tables) |
| Browser node | Research degraded; core data/rules/execution continue | Reinstall AdsPower, restore profile metadata/proxy config, register node |
| Object storage | Media previews degraded; analytics/execution continue | Restore bucket/versioning; block new creative jobs until healthy |

Execution after DR: re-run approval expiry, revalidation and state drift — never blindly
replay approved executions.
