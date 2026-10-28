# ADR-003: Redis is not a durable source of truth

- Status: Accepted
- Date: 2026-08-10

## Context

Queues, locks and caches need speed; jobs need durability.

## Decision

Redis is used for queues/cache/locks only. Jobs are persisted (`job_runs`, execution
tables); queue reconciliation rebuilds work after Redis loss.

## Consequences

Queue loss is recoverable; duplicate delivery must be handled by idempotency keys.
