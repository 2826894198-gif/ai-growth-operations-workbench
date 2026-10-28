# ADR-004: Docker Compose first production topology

- Status: Accepted
- Date: 2026-08-10

## Context

Small team, moderate load; Kubernetes adds operational cost without immediate value.

## Decision

Single production control plane via Docker Compose (edge + data + execution networks),
with an isolated browser node.

## Alternatives

Kubernetes (deferred until scale or multi-host requirement).

## Consequences

Single-host limits must be respected; promote staging→production with immutable images.
