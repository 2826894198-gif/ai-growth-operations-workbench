# Rollback Runbook

Separate the three cases:

1. **Application rollback:** deploy previous image digest; DB unchanged.
2. **Database recovery:** restore from verified backup / PITR (not blind alembic downgrade).
3. **Provider execution compensation:** use PART 06 compensation review; never "undo" a
   platform action without revalidation.

Always record rollback in `releases.rollback_from` and audit.
