# Browser Node Recovery Runbook

1. Install AdsPower + browser worker.
2. Restore profile metadata and proxy config from secure backup.
3. Register/re-register node in `browser_nodes` (workspace allowlist).
4. Heartbeat online; run public snapshot smoke.
5. Do NOT restore cookies from unknown sources.
