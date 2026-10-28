# AI DTC Growth System · 增长运营工作台

**让 AI 建议走向可控执行：每次动作经过审批、校验和留痕，先在模拟环境完整跑通。**

把营销数据、确定性规则、AI 分析与多账号运营组织成一个增长工作台，覆盖数据质量、推荐证据、连接管理和执行审批，并以 mock 默认值提供可复现演示。

> 当前阶段：工程原型与合成数据演示；默认模拟服务、影子规则和关闭真实执行。

## 项目亮点

- 把数据、规则判断、AI 建议、审批、执行校验与审计连成完整路径。
- 在统一工作台组织账号连接、内容分析、推荐证据和执行队列。
- 用模拟数据重现业务流程，并为真实写入保留权限、校验和执行门槛。

## 技术实现

Python 3.12 · FastAPI · Celery · PostgreSQL · Redis · React / TypeScript / Vite / Tailwind · LangGraph · Playwright/CDP · Docker Compose / Caddy

- Makefile
- backend/app/main.py
- browser-worker/worker/main.py
- frontend/
- config/rules/
- infra/

## 快速开始

Docker Desktop、Python 3.12/uv、Node.js 22/npm；默认 mock provider，执行与外部写入关闭。

```sh
make bootstrap
make up-safe
make seed-safe
make verify-local
# Stop while preserving local fixture data:
make down
```

演示入口 http://127.0.0.1:15173；无需真实服务凭据。请先读 docs/LOCAL-BOOTSTRAP.md；合成广告、订单和指标不是实际经营成果。

## 目录导航

```text
.dockerignore
.gitignore
AGENTS.md
CHANGELOG.md
CODEOWNERS
LICENSES.md
Makefile
SECURITY.md
VERSION
backend/
browser-worker/
compose.dev.yaml
compose.prod.yaml
compose.staging.yaml
compose.yaml
config/
docker-compose.yml
docs/
evals/
fixtures/
frontend/
infra/
pyproject.toml
scripts/
tests/
```

## 交付状态与证据

- README.md
- docs/LOCAL-BOOTSTRAP.md
- docs/PART-02-IMPLEMENTATION-REPORT.md
- docs/PART-03-IMPLEMENTATION-REPORT.md
- docs/PART-04-IMPLEMENTATION-REPORT.md
- docs/PART-07-IMPLEMENTATION-REPORT.md

- 只读核查了 README 与 LOCAL-BOOTSTRAP，未重新运行全套测试或逐项核验全部实现报告。
- 不要将 mock 数据、合成 ROAS 或 demo 推荐宣称为真实商业成效。
- Instagram 页面仍明确 DEMO，OAuth/token/sync 需 live-tested 后才能改变状态。
- Part 01–04 的只读边界不能误称整个仓库永远无写路径；后续 execution 存在明确审批与 provider 写开关。
- 生产 GO 需要真实 Postgres/TLS/Secret Manager/OAuth 和 production-check，不能只凭 production 配置文件称已生产化。

本次整理的核验结果见 [仓库状态](docs/REPOSITORY_STATUS.md)，项目介绍口径见 [展示说明](docs/SHOWCASE.md)。

## 协作与使用

- 安装依赖前核对项目所需运行时，配置文件使用示例值；凭据和真实业务数据不进入 Git。
- 提交与反馈请见 [CONTRIBUTING.md](CONTRIBUTING.md)；敏感问题处理见 [SECURITY.md](SECURITY.md)。
- 许可证与第三方资源见 [RIGHTS.md](RIGHTS.md)。公开访问不等于获得所有素材的再分发许可。
