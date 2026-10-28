# API Version Upgrade Runbook

1. Read provider release notes + migration changes.
2. Update `META_GRAPH_API_VERSION` / `GOOGLE_ADS_API_VERSION` in TEST.
3. Run provider contract tests + golden suites against recorded fixtures.
4. Deploy capability-aware code before version switch.
5. Switch version in staging, validate, then production with rollback plan.
