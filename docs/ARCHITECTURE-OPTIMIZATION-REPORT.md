# 架构优化实施报告（依据外部评审）

> 依据：`AI-DTC-Growth-Automation-架构优化评审.md`（2026-08-10）
> 状态：P0 架构项已落地并测试；真实 Provider/Postgres 运行项按评审路线图移交 PART 07。

## 1. 完成内容

| 评审项 | 优先级 | 落地 | 验证 |
|---|---|---|---|
| Canonical Entity 注册表 | P0 | `entity_registry` / `external_entity_refs` / `entity_relations` + `EntityService`；规则/意图可携带 canonical ID，Provider 调用经 resolver | 单元测试通过 |
| 指标语义层 | P0 | `metric_definitions`（口径/分子分母/measurement_basis/新鲜度/owner/version）+ `MetricQueryService` 统一入口 | 单元测试通过 |
| 租户 RBAC | P0 | `users` / `workspace_memberships` / `brand_grants` / `account_grants` + API 权限依赖（角色→权限映射） | 单元测试通过 |
| 执行动作包绑定 | P0 | `action_package_hash`（entity+policy+credential+metric_snapshot+approval）；引擎执行前校验，变更即 APPROVAL_MISMATCH | 单元测试 + 34/34 smoke |
| 执行状态机收敛 | P0 | `INTENT_TRANSITIONS` / `JOB_TRANSITIONS` 状态机定义 + 转换校验 | 代码级 |
| CI 契约 | P0 | 17 社媒 + 34 执行黄金场景纳入 pytest 集成（进程级 CI 运行） | `pytest ../tests` 85 passed |
| Provider Control Plane | P1 | `provider_manifests`（auth/scopes/capabilities/rate_limit/health/api_version）+ `credential_refs`（READ/WRITE 分离，凭据仅引用） | API 可查 |
| Job Registry | P1 | `job_runs` / `job_attempts` / `job_events` / `outbox_messages` + 幂等/重试/事件服务 | 单元测试通过 |
| AI 收敛 | P1 | `DecisionAssistant`（query_metrics / explain_change / retrieve_rule_evidence / simulate_action / draft_execution_intent），只读只起草 | API 验证 |
| Recommendation Case | P1 | 案例状态机 DRAFT→SIMULATED→PENDING_APPROVAL→APPROVED→EXECUTED + 模拟影响 + 统一时间线 | API + 页面 |
| 前端 6 大工作域 | P1 | 导航收敛：今日决策 / 账号与渠道 / 内容与创意 / 建议与实验 / 执行与审计 / 数据与设置；共享 MetricCard / EntitySummary / EntityTimeline | 构建通过 |
| Kill Switch | P0 扩展 | 新增 WORKSPACE 范围熔断 | 代码级 |

## 2. 数据分层与唯一键

- Raw → Canonical → Semantic → Operational 四层已在代码中体现：
  - Raw：`raw_api_payloads`（既有）
  - Canonical：`dim_*` / `fact_*` / `content_*` / `entity_registry`
  - Semantic：`metric_definitions` + `MetricQueryService`
  - Operational：`recommendations` / `execution_*` / `connection_audits`
- `fact_ad_performance_daily.measurement_basis` 已加列，平台自报与第一方归因不再混为一谈。

## 3. 前端收敛

```text
今日决策      指挥中心（含 Decision Assistant）
账号与渠道    账号 / 连接中心 / 数据健康
内容与创意    内容智能 / 创意实验室
建议与实验    推荐案例（新页面）/ 实验 / 漏斗 / AI 智能
执行与审计    审批队列 / 执行队列 / 策略 / 熔断
数据与设置    设置 / 环境 / 规则控制台
```

推荐列表每条可打开“推荐案例”：规则证据 + AI 解释 + 模拟影响 + 审批/意图/任务 + 决策时间线。

## 4. 验证结果

```text
pytest ../tests           85 passed, 1 skipped
smoke-social              17/17（经 CI 测试包装）
smoke-execution           34/34（经 CI 测试包装）
前端 npm run build       通过
治理 API                  实体/指标/案例/决策助手/认证 全部 200
```

## 5. 移交 PART 07 的事项

- PostgreSQL 本地/CI 全量切换（本机无 Docker/Postgres，代码已 Postgres-first，配置默认即 Postgres）
- 真实只读连接（Meta/Shopify）与 Provider App 审核
- SSO/正式登录与 Session/Cookie 替代 X-User-Id header
- 凭据管理（密钥库/轮换/审计导出）
- CI 流水线（GitHub Actions）与 51 场景定时回归
