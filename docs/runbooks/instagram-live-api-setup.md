# Instagram Growth Intelligence — Live API 接入准备

状态：代码侧已具备 Business Login OAuth callback、加密 token vault、只读 Live sync 与 RAW snapshot；当前部署仍保持显式 DEMO，尚未宣称 Live。

这份清单用于把 Meta 应用、Instagram 专业账号、OAuth 回调和服务器密钥准备好。不要在没有通过预检、没有稳定 HTTPS 回调的情况下把 `INSTAGRAM_DEMO_MODE` 改成 `false` 来“试运行”。

## 1. 本项目采用的 API 路径

V1 推荐使用 **Instagram API with Instagram Login / Business Login for Instagram**：

- 账号必须是 Instagram Professional（Business 或 Creator）。
- 本监控只申请只读分析所需的 `instagram_business_basic` 和 `instagram_business_manage_insights`。
- 这条路径不要求为了本监控额外绑定 Facebook Page，也不把 Ads、Shopify、Revenue、ROAS 或购买归因带进 Instagram V1。
- API 版本统一读取 `META_GRAPH_API_VERSION`；不要新增或继续依赖 `INSTAGRAM_API_VERSION`。

官方入口：[Meta Instagram API Postman 文档](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)。官方文档同时列出了 Instagram Login 与 Facebook Login 两条路径；如果未来确实需要 Page/Meta Ads 资源，再单独评估 Facebook Login，不要混入本期只读监控。

## 2. 已在仓库准备好的内容

- `/api/v1/instagram/overview`、`/capabilities`、`/content` 以相同契约返回显式 DEMO 或已持久化 LIVE 数据；`POST /api/v1/instagram/sync` 只在 server-side Live mode 启用后执行只读同步。
- Connection Center 的 OAuth transaction、一次性 `state`、redirect allowlist、精确 GET callback 与 workspace 绑定。
- 授权码换 token、long-lived token exchange、`/me` account discovery，以及 `instagram_oauth_credentials` 的加密服务端保存；任何 API 响应都只返回不透明引用和连接状态。
- 读取请求使用 Bearer header，RAW payload 在写库前会剔除 token、secret、authorization 与 code 字段。
- Instagram 专用 scope manifest：只读 V1 不声明 `ADS_READ` 或付费归因能力。
- `META_GRAPH_API_VERSION`、OAuth 模式、App ID、secret reference、token reference、scope 和 callback 的环境变量模板。
- `make instagram-preflight`：只输出配置项状态，不输出任何 secret/token。

## 3. 你需要准备的 Meta 侧内容

在 Meta for Developers 中准备一个用于测试的应用，并把自己的 Instagram 专业账号加入测试范围：

| 项目 | 需要准备 | 说明 |
| --- | --- | --- |
| App | Meta App ID / App Secret | App ID 可用于配置；App Secret 只能放服务端密钥环境，不能发到聊天或前端。 |
| 产品 | Instagram API with Instagram Login / Business Login | 按 Meta 控制台当前名称启用对应产品。 |
| 账号 | Instagram Business 或 Creator | 个人账号不满足本监控的 Graph API 前提。 |
| 权限 | `instagram_business_basic`、`instagram_business_manage_insights` | V1 只读分析最小集合；不要先申请 Ads 或发布权限。 |
| 测试关系 | App Tester / 账号管理员或所有者 | 测试账号必须能完成授权并授予上述权限。 |
| Access Level | 自有/已加入 App 的账号可先用 Standard；服务非自有账号时再申请 Advanced | 是否需要审核取决于服务范围。 |
| 合规信息 | App 域名、隐私政策、数据删除/去授权回调 | 上线和审核前必须补齐真实域名与公开页面。 |

请只把以下非敏感信息交给我或填入本地模板：

```text
INSTAGRAM_APP_ID=你的 App ID
INSTAGRAM_OAUTH_REDIRECT_URI=最终使用的完整回调地址
Instagram 账号类型=Business 或 Creator
账号是否为 App 所有者/测试员=是/否
部署环境=本地 / staging / production
```

不要在聊天里发送 App Secret、access token、cookie 或截图中的完整敏感值。

## 4. 回调地址

先按环境准备一条精确地址；Meta 后台的地址必须与请求中的 `redirect_uri` 完全一致（协议、域名、端口、路径都不能临时改）：

```text
本地：
http://127.0.0.1:8000/api/v1/connections/instagram/oauth/callback

Staging：
https://<staging-host>/api/v1/connections/instagram/oauth/callback

Production（待定域名）：
https://<production-host>/api/v1/connections/instagram/oauth/callback
```

本地回调地址仅用于开发测试；Staging/Production 必须使用真实、稳定、可访问的 HTTPS 域名，不能使用 `example.com` 或 localhost。Meta 后台、`INSTAGRAM_OAUTH_REDIRECT_URI` 和 `OAUTH_REDIRECT_ALLOWLIST` 必须是同一个完整地址。当前仓库的 callback 路径是可运行的，但不会替你创建或暴露公网主机。

## 5. 服务器环境变量

以 `config/env/*.env.example` 为模板。最小配置形态如下：

```dotenv
APP_ENV=local
META_GRAPH_API_VERSION=v26.0
SOCIAL_PROVIDER_MODE=live
INSTAGRAM_SYNC_ENABLED=true
INSTAGRAM_DEMO_MODE=false
INSTAGRAM_OAUTH_MODE=instagram_login
INSTAGRAM_APP_ID=填入非敏感 App ID
INSTAGRAM_APP_SECRET_REFERENCE=env:INSTAGRAM_APP_SECRET
INSTAGRAM_TOKEN_ENCRYPTION_KEY_REFERENCE=env:INSTAGRAM_TOKEN_ENCRYPTION_KEY
INSTAGRAM_ACCESS_TOKEN_REFERENCE=env:INSTAGRAM_ACCESS_TOKEN
INSTAGRAM_REQUIRED_SCOPES=instagram_business_basic,instagram_business_manage_insights
INSTAGRAM_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/api/v1/connections/instagram/oauth/callback
OAUTH_REDIRECT_ALLOWLIST=http://127.0.0.1:8000/api/v1/connections/instagram/oauth/callback
```

注意：

- `INSTAGRAM_APP_SECRET`、`INSTAGRAM_TOKEN_ENCRYPTION_KEY` 与用户 token 只存在后端运行环境/SecretProvider，永不返回前端。
- 真实 OAuth 完成后，token 会加密写入 `instagram_oauth_credentials`；连接表仅保留 `vault://...` 不透明引用。不能把 token 填入数据库 JSON、日志、fixture 或 React 状态。
- `INSTAGRAM_ACCESS_TOKEN_REFERENCE` 仅为旧 generic adapter 保留；Business Login 正常路径不要求预先填 token，而是由 OAuth callback 产生并写入加密 vault。
- `INSTAGRAM_DEMO_MODE=true` 只用于当前本地演示；Live 未完成前保持 DEMO。

## 6. 真实接入时的调用链

```text
设置页点击连接
  → 后端生成一次性 state（Instagram Business Login 当前授权参数不使用 PKCE）
  → 跳转 Meta/Instagram Login
  → 后端 GET callback 校验 state / redirect / code
  → 服务端交换短期 code 与 long-lived token，并加密保存 opaque token reference
  → /me 获取 Instagram professional account
  → 账号发现与用户确认 link
  → 拉取 media、account insights、media insights
  → Raw snapshot
  → Derived metrics / baseline / health / rules
  → /api/v1/instagram/* 返回带 source_mode、layer、availability、caveats 的结果
```

任何 API 空数组、权限不足、账号不支持、指标暂不可用，都保留为不可用/缺失；不能转成 `0`，也不能因为接通了 API 就生成 Ads、收入、ROAS 或购买归因。

## 7. 接入验收顺序

1. 填入 App ID 和服务端 SecretProvider reference。
2. 在 Meta 后台登记精确 callback，添加测试员/专业账号。
3. 运行 `make instagram-preflight`，先通过配置检查。
4. 完成一次授权，确认 `/me` 返回账号 ID 与类型，且连接页面只显示“已配置”而不显示 token。
5. 发起一次 `POST /api/v1/instagram/sync`，确认写入 `instagram_sync_runs`、`raw_api_payloads`、account/media snapshots 与 capability matrix。
6. 用空指标/权限拒绝/Insights 为空的响应跑回归测试；这些场景必须保留 `null + availability`。
7. 再把页面从 DEMO 切到 LIVE，并重新做 1440px/390px 实际视觉验收。

## 8. 当前明确不需要准备的东西

- AdsPower 指纹浏览器：它是浏览器执行节点，不是 Instagram Graph API 的数据凭据。
- Meta Ads 账户、广告 token、Shopify token、Revenue/ROAS 数据：不属于本期 Instagram Growth Intelligence V1 的接入前提。
- 购买归因或兴趣标签：Instagram Insights 本身不能证明这些结论，本项目不会伪造。

## 9. 交给开发实现时的最小信息包

准备好下面 5 项后，就可以进入 Live OAuth 实现和联调：

1. `INSTAGRAM_APP_ID`
2. App Secret 已在本地/服务器 SecretProvider 中配置（只告知“已配置”，不要发送值）
3. 最终 callback URL
4. 一个可登录的 Instagram Business/Creator 测试账号
5. 该账号是否只服务自有资产，还是要支持其他客户账号
