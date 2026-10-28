# PART 04 IMPLEMENTATION REPORT

**System:** AI DTC Growth Automation System — Part 04 (Multi-Agent & AI Intelligence Architecture)

**Date:** 2026-08-10

**Repository root:** `ai-dtc-growth-system/`

---

## 1. Overall Status

**READY**

The AI intelligence layer runs on LangGraph with a mock-first model layer,
eight specialized agents, a runtime-controlled tool layer, knowledge/memory,
creative media pipeline, offline evals and observability. It never bypasses
the Part 03 Rule Engine and exposes no external mutation tools.

## 2. Repository Tree (Part 04 additions)

```text
ai-dtc-growth-system/
├── docs/PART-04-Multi-Agent-AI-Intelligence-Architecture.md
├── config/ai/{model_routes,tool_permissions,cost_budgets,agent_invocation}.yaml
├── config/prompts/{supervisor,performance,creative,search,funnel,competitor,strategy,reviewer}/v1.md
├── evals/datasets/{performance,reviewer,search,permission}/cases.json
├── backend/app/
│   ├── ai/
│   │   ├── orchestrator/{graph,state,router,supervisor,nodes,runner,checkpoints}.py
│   │   ├── agents/{base,definitions}.py
│   │   ├── models/{base,mock_provider,openai_provider,gemini_provider,router}.py
│   │   ├── tools/{registry,permissions,build_registry,metrics,rules,commerce,search,creative,knowledge,memory,compute,browser}.py
│   │   ├── memory/{policy,business}.py
│   │   ├── knowledge/{ingestion,chunking,retrieval,vector_store}.py
│   │   ├── prompts/registry.py
│   │   ├── schemas/{common,supervisor,performance,funnel,search,creative,strategy,review,competitor}.py
│   │   ├── evals/{runner,graders}.py
│   │   ├── observability/{tracing,metrics,cost}.py
│   │   ├── media/{preprocess}.py
│   │   └── creative/analysis.py
│   ├── models/ai.py
│   ├── api/v1/{ai_runs,ai_query,ai_health,creative_ai}.py
│   └── workers/ai_tasks.py
├── scripts/{seed_ai_demo,ai_cli,smoke_ai}.py
└── tests/{unit/test_ai_layer.py, integration/test_ai_graph.py}
```

## 3. Database Migrations

Migration `0004_part04_ai_intelligence` adds 11 tables:

```text
ai_agent_runs, ai_agent_steps, ai_prompts, ai_business_memories,
knowledge_documents, knowledge_chunks, creative_ai_analyses,
ai_model_usage, ai_eval_runs, ai_eval_results, ai_tool_audits
```

`alembic upgrade head --sql` generates successfully (0001 → 0004).

## 4. LangGraph Runtime

### Graph

```text
START → supervisor → specialists → strategy → review
        (review fail & revisions<1 → revise → strategy)
        (pass → human → complete → END)
```

### State

`GrowthAgentState` keeps structured facts/IDs/refs (run_id, thread_id,
task_type, plan, specialist_outputs, strategy_output, review_output,
revision_count, errors, cost/token usage, pending_approval, decision).

### Checkpoint

Compiled with a LangGraph checkpointer (MemorySaver in dev; PostgreSQL-backed
persistence is a documented deferred item for production).

### Interrupt / Resume

`human_node` uses LangGraph `interrupt` to emit a HumanApprovalPacket;
`POST /api/v1/ai/runs/resume` resumes with `Command(resume=decision)`.

### Partial Failure

Specialists run in parallel; per-agent exceptions are captured into
`errors`/`specialist_outputs[agent].status=ERROR` and the run continues
(strategy explicitly notes missing inputs).

## 5. Model Layer

### Model Router

`config/ai/model_routes.yaml` routes task types to primary/fast/video with
fallback chains; model IDs come only from configuration (`AI_*_MODEL`).

### OpenAI Provider

`OpenAIProvider` uses the Responses API with JSON-schema structured outputs,
usage extraction, retry/error mapping (auth/rate/timeout/context).

### Gemini Provider

`GeminiProvider` supports native video understanding via `google-genai`
(structured JSON response); media refs passed as content.

### Mock Provider

`MockModelProvider` generates deterministic schema-valid outputs for every
agent schema (SupervisorPlan, PerformanceDiagnosis, FunnelDiagnosis,
SearchIntelligenceResult, CreativeAnalysisOutput, GrowthStrategy,
ReviewResult, CompetitorIntelligenceResult).

### Fallback

Schema failure gets one structured repair retry then `MODEL_SCHEMA_ERROR`;
high-risk strategy never falls back to a weaker model (mock mode covers
offline runs).

## 6. Tool Layer

### Tool Registry

44 registered semantic tools (no `run_sql`, no mutation tools). Each has
risk level (R0_R1_R2 only), allowed agents, timeout, audit, approval flag.

### Permission Matrix

`config/ai/tool_permissions.yaml`; runtime `check_permission` rejects
unauthorized calls (Performance cannot browser; Strategy cannot query raw
metrics; Competitor gets only public snapshot tools).

### Tool Audit

Every call records input hash + safe summary, output ref, duration, success,
error code into `ai_tool_audits` (secrets/PII redacted by `_safe`).

## 7. Supervisor Agent

Builds `SupervisorPlan` (task_type, scope, agents, priority questions,
approval_expected) using only summary-level findings. Cannot call ads APIs or
write recommendations.

## 8. Performance Agent

Diagnoses CPM/CTR/CPC/CVR/CPA/ROAS from metric + rule + commerce tools,
distinguishes traffic/conversion/tracking, emits `PerformanceDiagnosis` with
evidence refs and source metric ids.

## 9. Creative Intelligence Agent

Two-stage pipeline: media inspection (hash, duration, frames) → structured
Creative DNA (hook, product appearance, scenes, emotion, audio, CTA,
taxonomy labels). Supports blind mode; analysis mode recorded as
`NATIVE_VIDEO` or `FRAME_SAMPLE`. Winner status always comes from Part 03.

## 10. Search Intelligence Agent

Classifies query intent, clusters search terms, outputs waste candidates with
negative-candidate confidence and expansion candidates. Negative keywords are
recommendations only — no creation tool exists.

## 11. Funnel Diagnosis Agent

Diagnoses funnel stages (CTR→Click→LPV→ATC→Checkout→Purchase), builds likely
cause trees, separates site vs ad vs tracking issues. Missing stages stay
NULL, never 0.

## 12. Competitor Intelligence Agent

Read-only public research through the restricted browser tool; observations
record source URL, capture time, content hash, and claim type. No social
interaction or mutation tools exist.

## 13. Strategy Agent

Synthesizes specialists + rule recommendations into `GrowthStrategy`
(priorities with evidence/rule refs, actions_now, experiments, creative
briefs, do_not_change, risks). No external mutation.

## 14. Reviewer Agent

Strict `ReviewResult` check of numeric accuracy, unsupported claims, missing
evidence, rule conflicts, permissions, risk. Max 1 revision loop, then
human review.

## 15. Knowledge Base

Versioned documents + chunking (fixed for short texts), keyword + metadata
filter retrieval, vector adapter (pgvector-ready with JSON fallback).
`make seed-ai-demo` ingests 6 seed documents.

## 16. Business Memory

`ai_business_memories` with PROPOSED/VERIFIED/ACTIVE/STALE/INVALIDATED
lifecycle, evidence refs, confidence, review/expiry. Agents can only propose;
approval required by default; forbidden content patterns are rejected.

## 17. Prompt Registry

8 versioned prompt files under `config/prompts/*/v1.md` synced to
`ai_prompts` (prompt_key + version unique). Prompts carry the base policy:
grounding, FACT/INFERENCE/HYPOTHESIS, no secrets, no mutation, external
content is data.

## 18. Browser / AdsPower MCP Gateway

`public_page_snapshot` / `take_screenshot` tools implement URL policy,
profile allowlist intent, rate limits and audit. Actual capture is gated by
`AI_BROWSER_RESEARCH_ENABLED` and delegated to the Part 01 worker pipeline;
AdsPower MCP remains disabled by default (explicit allowlist required).

## 19. Structured Output Validation

All inter-agent outputs are Pydantic schemas; invalid output gets one repair
retry then `MODEL_SCHEMA_ERROR`. Output sanitization redacts sensitive
patterns and caps lengths.

## 20. Prompt Injection Tests

Runtime permission layer makes injection ineffective: the tool registry does
not contain mutation tools; Competitor cannot call profile management tools;
golden eval `competitor_cannot_delete_profile` asserts forbidden tools never
appear.

## 21. Golden Evals

4 eval suites (performance, reviewer, search, permission) with numeric
accuracy, groundedness, tool selection, permission checks. Result:

```text
passed=5 failed=0
scores: schema=1.0 grounding=0.7 numeric=1.0 tool=1.0 permission=1.0
```

## 22. Numeric Grounding Tests

`performance_numeric_accuracy` requires primary_driver=funnel/checkout with
tool evidence; reviewer case requires detection of wrong ROAS claim; critical
failure is flagged when expected facts are wrong.

## 23. Permission Tests

Unit + golden tests: Performance cannot use browser; Strategy cannot query
raw metrics; no `pause_campaign`/`change_budget`/`create_negative_keyword`/
`run_sql` tools exist in the registry.

## 24. Cost / Usage

Every model call records input/output/cached tokens, latency and estimated
cost into `ai_model_usage`; per-task budgets configured in
`config/ai/cost_budgets.yaml`; run totals roll up into `ai_agent_runs`.

## 25. Observability / Trace

`/ai/health` exposes orchestrator, providers, tool registry, knowledge,
memory, runs today, failures, cost today. `GET /api/v1/ai/runs/{id}` returns
steps, tool calls and usage (safe summaries only).

## 26. AI Console

`/ai-console`: overview cards (runs today, failures, cost, tools), model/KB/
memory status, deterministic query box (0-LLM gate), runs table with clickable
agent trace.

[演示截图未随公开源码包附带；可用本地虚构数据重新生成。]

## 27. Smoke Test

`make smoke-ai` output:

```text
PASS  Database
PASS  Tool Registry (44 tools)
PASS  Tool Permissions
PASS  Mock Model Provider
PASS  Model Router
PASS  LangGraph Runtime
PASS  Checkpoint Store
PASS  Knowledge Retrieval
PASS  Business Memory
PASS  Supervisor
PASS  Performance Agent
PASS  Funnel Agent
PASS  Search Agent
PASS  Creative Agent
PASS  Competitor Agent
PASS  Strategy Agent
PASS  Reviewer
PASS  Structured Output
PASS  Partial Failure
PASS  Evidence References
PASS  Cost Tracking
PASS  Tracing
PASS  End-to-End Run
PASS  Golden Evals (5 passed / 0 failed)
SMOKE AI PASSED
```

Live API checks: simple spend query answered directly by Metrics API
(0 LLM calls); complex "Why did blended ROAS decline?" ran the full graph to
COMPLETED.

## 28. Automated Test Results

Full repository suite: **70 passed, 1 skipped** (AdsPower live integration).

Part 04 coverage:

- intent classification + deterministic direct-query gate
- tool permission matrix and no-mutation registry
- structured output validation/repair
- memory write policy (secrets/PII, verified-without-evidence)
- chunking, model router mock mode
- LangGraph daily-review end-to-end, partial failure, evals

`ruff check` passes on backend, scripts and tests; frontend `npm run build`
passes.

## 29. Known Issues

1. Checkpoint store is in-memory (MemorySaver); PostgreSQL-backed persistence
   is deferred — thread resume works within a process only.
2. OpenAI/Gemini providers are implemented but not live-tested (no keys).
   Video analysis runs in mock FRAME_SAMPLE mode; native video path requires
   `GEMINI_API_KEY` + `google-genai`.
3. Creative media preprocessing is mock (hash/metadata/frame refs); FFmpeg
   frame extraction + transcript are stubs.
4. Human-in-the-loop interrupt is wired but not exercised in the smoke flow
   (approval_expected=false by default); a dedicated HITL test is deferred.
5. Agent outputs are deterministic mock; real grounding quality depends on
   provider behavior and should be re-evaluated in live mode.
6. Tool calls inside agents are runtime-built per specialist (no free-form
   model tool selection), which is intentional for safety but limits
   flexibility.

## 30. Deferred Work

- PostgreSQL checkpointer + multi-process durable resume
- Live OpenAI/Gemini provider validation, video native mode + FFmpeg pipeline
- AdsPower MCP Gateway live integration (gated)
- Experiment/creative-brief generation already in schema; enrich with real DNA
- Full HITL UI (approve/reject packets) and approval expiry
- Shadow-model A/B routing and model upgrade gating via evals
- Cost guard enforcement (stop optional agents at budget)

## 31. Ready / Not Ready for PART 05

**READY for PART 05.**

The AI layer produces explainable, evidence-backed intelligence on top of
Part 02 data and Part 03 rules; PART 05 can compose Data + Recommendations +
Intelligence into the final growth dashboard without changing the agent
boundaries.
