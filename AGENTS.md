# Codex Working Contract (PART 07 §273-§291)

## Rules

1. **Respect part contracts.** Do not silently weaken PART 06 execution safety:
   Recommendation → Approval → Frozen Intent → Revalidation → Policy → Mutation →
   Verification → Audit → Compensation. No Agent/LLM may call provider mutation.
2. **PostgreSQL is source of truth.** Redis is cache/queue only. Never store durable
   business state solely in Redis.
3. **Migrations.** New schema changes require a numbered Alembic migration
   (`000N_*.py`) and must be expand/contract compatible. Do not rename critical
   columns directly; use expand/contract + backfill.
4. **Secrets.** Never commit secrets; never log tokens/cookies/keys/PII. Use
   `credential_reference` and `SecretProvider`.
5. **Provider versions** are configuration (`META_GRAPH_API_VERSION`, `GOOGLE_ADS_API_VERSION`),
   never scattered literals in business logic.
6. **Tests.** Any execution/rules/AI change must pass the golden suites:
   `make smoke-execution`, `make smoke-social`, and `pytest ../tests`.
7. **No unrequested rewrites.** Do not refactor whole modules without a task that
   asks for it. Keep the module boundary (control plane / workers) intact.
8. **Live write tests** require `ALLOW_LIVE_EXECUTION_TESTS=true`, a test account, an
   allowlisted resource and manual invocation; CI sets it to false and refuses.
9. **Workspace isolation** is a security boundary. Every scope-aware query filters by
   workspace membership; RLS is defense in depth.
10. **Observability** never blocks requests; structured JSON logs include
    request_id/trace_id/workspace_id/execution_id.

## Sensitive paths (require extra care)

- `backend/app/execution/` — execution safety chain
- `backend/app/api/v1/execution_*` — execution APIs
- `backend/app/services/social/connection_service.py` — OAuth/credentials
- `backend/app/core/secrets.py` — secret resolution
- `infra/postgres/rls.sql` — tenant isolation
- `migrations/` — schema changes
