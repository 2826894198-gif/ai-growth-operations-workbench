# ADR-005: AdsPower as local-only browser node

- Status: Accepted
- Date: 2026-08-10

## Context

Browser research and environment work must not expose AdsPower to the public internet.

## Decision

Browser node runs AdsPower on node-localhost; worker connects outbound to the control
plane with node identity + secret. Browser automation is an operator-assisted fallback,
not an execution path.

## Consequences

No public :50325; node registry + heartbeat required.
