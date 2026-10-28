# Secret Rotation Runbook

1. Create new secret in secret manager (new reference/version).
2. Deploy dual/compatible config.
3. Validate (health probes, provider call).
4. Switch references, revoke old, audit.

Provider tokens: new authorization → validate → switch reference → revoke old.
Provider app secrets: planned change, staging validation, callback test, production switch.
