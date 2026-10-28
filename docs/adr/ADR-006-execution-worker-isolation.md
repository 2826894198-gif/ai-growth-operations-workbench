# ADR-006: Execution worker isolation

- Status: Accepted
- Date: 2026-08-10

## Context

Only the execution layer may mutate advertising platforms.

## Decision

A dedicated execution worker owns write credential references, execution tables and
queues. It has no browser, no arbitrary shell, no AI prompts; non-root + read-only FS.

## Alternatives

Running mutations in API/AI workers (rejected: permission and blast radius).

## Consequences

Deployment and secrets must keep worker credentials separate from read credentials.
