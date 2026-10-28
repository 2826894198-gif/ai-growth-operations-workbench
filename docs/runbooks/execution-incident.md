# Execution Incident Runbook

1. **Stop:** enable kill switch (global or provider/account/action scope).
2. **Classify:** duplicate mutation? unauthorized? verification spike? unknown outcome?
3. **Investigate:** read execution audit + events; check provider request id.
4. **Resolve:** compensation review (manual by default) or revalidation + new approval.
5. **Record:** incident record + postmortem; keep audit append-only.

P1: verification failure spike >3/5m, duplicate detected, unauthorized attempt.
