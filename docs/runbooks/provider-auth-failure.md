# Provider Auth Failure Runbook

1. Mark connection REAUTH_REQUIRED; alert admin.
2. Verify scopes diff and token expiry.
3. Reauthorize through Connection Center (single-use OAuth transaction + PKCE).
4. Compare before/after scopes; if scope missing → CAPABILITY_DEGRADED.
5. Rediscover resources, relink existing external IDs, resync, health check.
