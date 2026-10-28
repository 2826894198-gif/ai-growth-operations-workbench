# OAuth Reauthorization Runbook

```text
mark REAUTH_REQUIRED → notify admin → reauthorize → compare scopes
→ discover resources → relink existing IDs → sync → health
```

Never create duplicate accounts: match `external_account_id` on reconnect.
