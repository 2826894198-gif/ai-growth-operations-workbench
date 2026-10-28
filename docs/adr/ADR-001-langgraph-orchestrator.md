# ADR-001: LangGraph as primary AI orchestrator

- Status: Accepted
- Date: 2026-08-10

## Context

The AI layer needed deterministic orchestration, checkpointing and tool governance.

## Decision

Use LangGraph for orchestration with a controlled tool registry. PART 07 adds a
single `DecisionAssistant` path as the recommended production entry point.

## Alternatives

Plain function chains (no checkpoint/retry), CrewAI (less deterministic control).

## Consequences

Graph is explicit and testable; tool permissions must be enforced at the registry.
