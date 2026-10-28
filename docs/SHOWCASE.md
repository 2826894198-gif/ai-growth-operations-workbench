# AI DTC Growth System · 增长运营工作台 · 项目展示

## 一句话介绍

让 AI 建议走向可控执行：每次动作经过审批、校验和留痕，先在模拟环境完整跑通。

## 项目价值

把营销数据、确定性规则、AI 分析与多账号运营组织成一个增长工作台，覆盖数据质量、推荐证据、连接管理和执行审批，并以 mock 默认值提供可复现演示。

## 最值得展示的能力

- AdsPower Local API、Playwright/CDP Worker 与 Redis 配置锁
- Meta/Google/Shopify 数据连接与数据质量检查
- 52 条种子规则、证据、置信度、冲突处理和冷却

## 展示依据

- README.md
- docs/LOCAL-BOOTSTRAP.md
- docs/PART-02-IMPLEMENTATION-REPORT.md
- docs/PART-03-IMPLEMENTATION-REPORT.md
- docs/PART-04-IMPLEMENTATION-REPORT.md
- docs/PART-07-IMPLEMENTATION-REPORT.md

## 说明范围

当前阶段：已有独立 GitHub 仓库，本地实现覆盖文档 Part 01–07；应同步现有仓库而非重复创建。默认 mock provider、SHADOW 规则与执行关闭；真实生产 GO 仍需基础设施和集成验收。

- 只读核查了 README 与 LOCAL-BOOTSTRAP，未重新运行全套测试或逐项核验全部实现报告。
- 不要将 mock 数据、合成 ROAS 或 demo 推荐宣称为真实商业成效。
- Instagram 页面仍明确 DEMO，OAuth/token/sync 需 live-tested 后才能改变状态。
- Part 01–04 的只读边界不能误称整个仓库永远无写路径；后续 execution 存在明确审批与 provider 写开关。
- 生产 GO 需要真实 Postgres/TLS/Secret Manager/OAuth 和 production-check，不能只凭 production 配置文件称已生产化。

对外演示使用合成数据。源码、演示、历史验收记录与实时线上状态分别说明；任何效果数字都需要可追溯的测量记录。
