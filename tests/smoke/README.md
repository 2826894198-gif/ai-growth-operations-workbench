# Smoke Test

The live smoke test lives in the browser worker package:

```bash
cd browser-worker
source .venv/bin/activate
SMOKE_PROFILE_ID=<ads-power-profile-id> python -m worker.main smoke
```

Optional overrides:

- `SMOKE_PROFILE_NAME` — pick a profile by name instead of id
- `SMOKE_ALLOW_NO_PROXY=1` — allow a profile without a proxy (not recommended)

The command exits `0` on success and non-zero on failure. It executes:

```text
AdsPower API -> Profile Found -> Proxy -> Country US ->
Browser Launch -> CDP Connect -> Page Load -> Screenshot -> Browser Close
```
