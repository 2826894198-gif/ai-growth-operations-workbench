# ADR-002: PostgreSQL as durable source of truth

- Status: Accepted
- Date: 2026-08-10

## Context

Multiple workers and long-running execution state need one authoritative store.

## Decision

All durable business state lives in PostgreSQL (Alembic migrations). SQLite remains
a demo-only fallback; local/CI move to Postgres.

## Alternatives

MySQL, document stores, SQLite for production (rejected: concurrency/JSON/RLS gaps).

## Consequences

Expand/contract migrations and RLS become the safety mechanism; backup/restore discipline
is mandatory.
