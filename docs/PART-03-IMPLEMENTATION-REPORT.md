# PART 03 IMPLEMENTATION REPORT

**System:** AI DTC Growth Automation System — Part 03 (Growth Rule Engine, Decision Guardrails & Rule Simulation)

**Date:** 2026-08-10

**Repository root:** `ai-dtc-growth-system/`

---

## 1. Overall Status

**READY**

The Growth Rule Engine is deterministic, versioned, auditable and read-only:
it reads CORE/MART/feature data and emits structured recommendations. No
provider write path, LLM decision path, or auto-execution exists.

## 2. Repository Tree (Part 03 additions)

```text
ai-dtc-growth-system/
├── docs/PART-03-Growth-Rule-Engine.md
├── config/rules/
│   ├── defaults.yaml
│   ├── core_safety.yaml
│   ├── meta_performance.yaml
│   ├── google_search.yaml
│   ├── funnel.yaml
│   ├── commerce.yaml
│   └── cross_channel.yaml
├── backend/app/
│   ├── rules/
│   │   ├── engine.py  evaluator.py  registry.py  operators.py
│   │   ├── context.py  result.py  audit.py
│   │   ├── features/{registry,windows,readiness,marketing,commerce,funnel,google,account,anomalies}.py
│   │   ├── guards/{freshness,sample,attribution_delay,learning,recent_change,cooldown,experiment,runner}.py
│   │   ├── conflict/{resolver,policies}.py
│   │   ├── confidence/{scorer,components}.py
│   │   ├── anomaly/{rolling,zscore,mad}.py
│   │   ├── simulation/{replay,simulator}.py
│   │   └── recommendations/{builder,dedup,risk}.py
│   ├── models/rules.py
│   ├── api/v1/{rules,recommendations,simulations,rule_health}.py
│   └── workers/rule_tasks.py
├── scripts/{rules_load,rules_evaluate,rules_replay,rules_simulate,smoke_rules}.py
└── tests/
    ├── unit/{test_rules_operators,test_rules_windows,test_rules_guards,test_rules_conflict,test_rules_confidence}.py
    ├── rules/test_golden_scenarios.py + scenarios/*.json
    └── integration/test_rules_engine.py
```

## 3. Database Migrations

Migration `0003_part03_rule_engine` adds 13 tables:

```text
business_target_profiles
rule_definitions            (unique rule_key + version)
rule_parameters             (scoped overrides, source SEED/MANUAL)
rule_evaluation_runs
rule_evaluations            (context/feature snapshots + confidence + reasons)
recommendations             (evidence, supporting rules, suppressed reasons)
recommendation_feedback
rule_conflict_policies
active_experiments
creative_performance_labels
campaign_strategy_labels
entity_change_events
rule_audit_logs
```

`alembic upgrade head --sql` generates successfully (0001 → 0003).

## 4. Rule Engine Core

- `engine.run_evaluation()`: schedules (INTRADAY/DAILY/WEEKLY/MANUAL/REPLAY/SIMULATION),
  entity discovery per evaluation level, batch feature loading, per-rule failure
  isolation (ERROR result never aborts the run), run statistics.
- `evaluator.evaluate_rule()`: guards → conditions → trigger/evidence/confidence.
- `registry.py`: YAML packs + DB overrides; versioned `rule_definitions`.
- No arbitrary Python in rules — only the operator set is callable.

## 5. Rule DSL

YAML per rule:

```yaml
guards: {min_age_hours, data_freshness_minutes, min_clicks, attribution_delay_minutes, ...}
conditions:
  all:
    - {metric: spend_3d, operator: target_multiple_gte, target: target_cpa, multiple: 2.0}
action: {type: REVIEW_PAUSE, reason: NO_PURCHASE_BURN, risk: MEDIUM}
cooldown_minutes: 1440
```

Operators: `eq neq gt gte lt lte between percent_change_gt/lt ratio_gt/lt
target_multiple_gt/gte/lt/lte zscore_gt/lt is_null not_null`.

## 6. Feature Registry

`rules/features/registry.py` documents 40+ named features (spend/purchases/CTR/
CPA/ROAS/CVR/frequency/window changes/z-scores/funnel stages/search-term/keyword/
account/commerce/readiness). Features are built in batches by
`features/*.py` (one query per window per entity group — no N+1 per metric).

## 7. Business Target Profiles

`business_target_profiles` supports GLOBAL/PLATFORM/ACCOUNT/CAMPAIGN scopes with
priority Campaign > Account > Platform > Global. Fields: target_cpa,
target_roas, break_even_roas, target_aov, gross_margin_rate, daily spend caps,
refund thresholds.

## 8. Guards

### Freshness
- `DATA_STALE` blocks rules when source lag > threshold; Data rules themselves
  are not blocked (they are the detector).

### Sample
- Reliability score (spend/clicks/purchases/active-duration maturity); minimum
  age/clicks/purchases/spend; purchase minimum only when the rule asks for it
  (search-term/keyword rules use their own sample semantics).

### Attribution Delay
- `ATTRIBUTION_DELAY` blocks high-impact actions for new entities.

### Recent Change
- `RECENT_CHANGE_COOLDOWN` suppresses scale/kill after budget/bid/creative
  changes read from `entity_change_events`.

### Learning
- `LEARNING_PROTECTION` suppresses scale and downgrades aggressive kill;
  CRITICAL safety rules bypass learning/experiment/recent-change guards.

### Experiment
- `EXPERIMENT_PROTECTION` suppresses variable-changing actions for entities in
  active experiments.

### Cooldown
- `COOLDOWN` deduplicates by entity+action+reason with severity escalation;
  REPLAY/SIMULATION runs ignore cooldown (deterministic replay).

## 9. Meta Rule Pack

15 rules implemented: No Purchase Burn, CPA Overshoot, Strong Performer, Scale
Candidate, Scale Cooldown, Creative Fatigue, CTR Deterioration, Frequency
Pressure, High Click Low Purchase, Low CTR, CPM Shock, Delivery Collapse,
Learning Protection, Audience Saturation, Winner Creative.

Creative fatigue uses multi-signal evidence (CTR drop + frequency + CPA trend),
never frequency alone.

## 10. Google Rule Pack

15 rules implemented: No Conversion Burn, CPA Overshoot, Search Term Waste,
Negative Keyword Candidate (recommendation only, never executed), Strong
Keyword, Keyword Waste, CPC Shock, CTR Weakness, CVR Collapse, Search Term
Expansion Candidate, Budget Constrained, PMax Base Efficiency, Brand/Non-brand
Guard, Match Type Drift, Conversion Tracking Anomaly.

Semantic waste detection uses a configured exclusion dictionary; negative
keyword output always includes candidate term + review flag.

## 11. Funnel Rules

6 rules: Low CTR, Click→LPV, LPV→ATC, ATC→Checkout, Checkout→Purchase, High
CTR Low Purchase. Missing stages stay NULL (capability unavailable), never 0.

## 12. Commerce Rules

5 rules: Revenue Drop, Refund Spike, AOV Drop, Product Mix Signal, Inventory
Capability Guard (disabled until INVENTORY capability exists).

## 13. Cross-channel Rules

5 rules: Blended ROAS Guard, Spend vs Revenue Divergence, Attribution Overlap
Caution, Channel Concentration, Total Daily Spend Guard (CRITICAL). Platform
attributed conversions are never summed as actual orders.

## 14. Anomaly Detection

`anomaly/rolling.py`, `zscore.py`, `mad.py`: rolling baseline, mean/std z-score,
median/MAD robust z-score; percent-change helpers. Used for CPM/CPC shocks and
account-level velocity.

## 15. Confidence Engine

Rule-based score (0-1, not a calibrated probability):

```text
0.20 × data_freshness + 0.25 × sample_reliability + 0.25 × rule_strength
+ 0.20 × signal_agreement + 0.10 × cross_source - penalties
```

Bands: LOW <0.40 · MEDIUM 0.40-0.69 · HIGH 0.70-0.84 · VERY_HIGH ≥0.85.
Component scores are stored per evaluation for explainability.

## 16. Conflict Resolver

Priority: DATA/TRACKING > SAFETY > COMMERCE > PAUSE/REDUCE > CREATIVE/AUDIENCE
> SCALE > OBSERVE. Policies: tracking blocks scale, learning blocks scale,
hard-spend beats learning, checkout issue downgrades creative kill/refresh,
search-term waste precedes campaign budget reduce. Resolution is deterministic.

## 17. Recommendation System

Structured contract: entity/platform/action/reason/severity/confidence/evidence/
supporting_rules/suppressed_reasons/approval_required/auto_execution_eligible.
Dedup merges same entity+action+reason into one recommendation with combined
evidence. Risk classification maps actions to LOW/MEDIUM/HIGH/CRITICAL and
approval flags; nothing executes.

## 18. Shadow Mode

`RULE_ENGINE_MODE=shadow` evaluates and records everything but does not create
formal recommendations. `make rules-load` seeds rules as SHADOW;
`make rules-shadow` force-resets to SHADOW. Promotion is explicit
(DRAFT → SHADOW → ACTIVE) via the Rules API.

## 19. Rule Simulation

`simulate_rule()` clones a candidate config (parameter overrides), evaluates
over a date range, reports trigger counts, and cleans up all temporary rows —
it never mutates active rules or recommendations. Verified by
"Simulation No Mutation" smoke check.

## 20. Historical Replay

`replay_rule()` evaluates day-by-day using data available at each as-of time.
Part 02 intraday snapshots are not yet used, so all replay results are labeled
`APPROXIMATE` (no look-ahead is introduced for daily facts). Replay is
deterministic: same as-of → same triggered count (cooldown ignored by design).

## 21. Rule Console

APIs:

```text
GET/POST /api/v1/rules..., /rules/{key}/enable|disable|shadow|activate
GET/PUT /api/v1/rules/{key}/parameters
POST /api/v1/rules/evaluate
GET /api/v1/recommendations, /{id}, acknowledge/approve/reject/feedback
POST /api/v1/rule-simulations, /rule-replays, GET /rule-simulations/{run_id}
GET /api/v1/rule-health
```

UI: `/rule-console` with Overview cards (active/shadow rules, open
recommendations, high severity), Recommendations table, Rules table and a
30-day Simulation form.

[演示截图未随公开源码包附带；可用本地虚构数据重新生成。]

## 22. Golden Scenario Results

9 golden scenarios under `tests/rules/scenarios/` — all pass:

```text
meta_no_purchase_burn        TRIGGERED REVIEW_PAUSE HIGH
meta_good_new_ad_learning    NO_DECISION (sample/learning protection)
meta_creative_fatigue        TRIGGERED REFRESH_CREATIVE
google_search_term_waste     TRIGGERED REVIEW_NEGATIVE_KEYWORD
google_tracking_failure      TRIGGERED CHECK_TRACKING
google_strong_keyword        TRIGGERED OBSERVE
shopify_refund_spike         TRIGGERED CHECK_REFUND
cross_channel_bad_blended_roas  TRIGGERED INVESTIGATE
data_stale                   TRIGGERED CHECK_DATA_SOURCE
```

## 23. Smoke Test Results

`make smoke-rules` output:

```text
PASS  Database
PASS  Metric Registry
PASS  Feature Registry
PASS  Rule Load (52 rules)
PASS  Rule Versioning
PASS  Mock Meta Rules (triggered=3)
PASS  Rule Evaluator
PASS  Recommendation System
PASS  Audit
PASS  Freshness Guard
PASS  Sample Guard
PASS  Learning Guard
PASS  Conflict Resolver
PASS  Recommendation Dedup
PASS  Confidence Engine
PASS  Historical Replay
PASS  Simulation
PASS  Simulation No Mutation
SMOKE RULES PASSED
```

Demo evaluation on 30-day mock data: 52 rules / 109 entities / 10 triggered /
0 suppressed; 9 open recommendations with 1 high severity.

## 24. Automated Test Results

Full repository suite: **61 passed, 1 skipped** (AdsPower live integration).

Part 03 coverage:

- operators (comparisons, null, target multiples, zero denominator)
- windows (rolling/previous/same-weekday, account-date semantics)
- guards (freshness, sample, attribution, learning, recent change, cooldown,
  escalation)
- conflict resolver (tracking vs scale, checkout vs pause, determinism)
- confidence (weights, penalties, bands)
- golden scenarios
- integration (engine pipeline, recommendations, replay determinism,
  simulation isolation)

`ruff check` passes on backend, scripts and tests; frontend `npm run build`
passes.

## 25. Known Issues

1. Replay is `APPROXIMATE` — intraday point-in-time snapshots are not yet
   consumed (Part 02 has the data; a follow-up can wire snapshots).
2. Account-level heuristics (`metric_discontinuity`, `tracking_loss_signal`,
   `conversion_tracking_anomaly`) are simple and should be calibrated with real
   account data.
3. Creative labels are evaluated but not yet written to
   `creative_performance_labels` (META_WINNER_CREATIVE emits a recommendation;
   label persistence is a small follow-up).
4. Funnel stages depend on Meta action availability; Google funnel stages are
   not sourced yet.
5. Rule health auto-pause on suspicious trigger-rate spikes is not implemented
   (first version only surfaces metrics via `/rule-health`).
6. Simulation runs synchronously in the API (fine at current scale); a queued
   worker variant is provided (`rules.simulate`).
7. Live business-target calibration (HISTORICAL_CALIBRATION) is designed but
   not yet populated.

## 26. Deferred Work

- Point-in-time replay from `fact_ad_performance_snapshots`
- Creative performance label persistence + lifecycle transitions
- Operator feedback → calibration pipeline (no auto parameter changes)
- Rule health alerting/auto-pause
- Google funnel stages and PMax query-level rules
- Experiment significance engine (Bayesian/sequential) — later
- MMM (Meridian/Robyn) interface reserved

## 27. Ready / Not Ready for PART 04

**READY for PART 04.**

PART 04 (Multi-Agent & AI Intelligence) may consume: recommendations, rule
evaluations, evidence, CORE/MART, creative metadata, search-term data and
browser tool results — but cannot bypass the deterministic Rule Engine for
high-impact decisions.
