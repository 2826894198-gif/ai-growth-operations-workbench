import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ErrorState } from "../components/common/ErrorState";
import { HealthStatusBadge } from "../components/health/HealthStatusBadge";
import { Spinner } from "../components/Spinner";
import { TimeSeriesChart } from "../components/charts/v2/TimeSeriesChart";
import { useScope } from "../domain/scope";

type Tab = "overview" | "events" | "data" | "content" | "connection";

const TABS: Array<{ key: Tab; label: string }> = [
  { key: "overview", label: "概览" },
  { key: "events", label: "检测记录" },
  { key: "data", label: "数据复盘" },
  { key: "content", label: "视频数据" },
  { key: "connection", label: "连接信息" },
];

function valueText(value: unknown, type: "count" | "money" | "ratio" = "count") {
  if (value == null) return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  if (type === "money") return `$${number.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  if (type === "ratio") return `${number.toFixed(2)}×`;
  return number.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function formatDate(value: unknown) {
  if (!value) return "未记录";
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
}

function percentText(value: unknown) {
  if (value == null) return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${(number * 100).toFixed(1)}%`;
}

function engagementRate(row: Record<string, unknown>) {
  const views = Number(row.organic_views || 0);
  if (!views) return null;
  return ["likes", "comments", "shares", "saves"].reduce((sum, key) => sum + Number(row[key] || 0), 0) / views;
}

export function AccountDetail() {
  const { id } = useParams();
  const { scope, setScope } = useScope();
  const [overview, setOverview] = useState<Record<string, unknown> | null>(null);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [content, setContent] = useState<Record<string, unknown> | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [contentDays, setContentDays] = useState(30);
  const [contentType, setContentType] = useState("ALL");
  const [contentSort, setContentSort] = useState("views");
  const [contentLoading, setContentLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingEvent, setUpdatingEvent] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError("");
    const [overviewResult, healthResult] = await Promise.allSettled([
      api.accountOverview(id, 30, scope.workspaceId),
      api.accountHealthDetail(id, scope.workspaceId),
    ]);
    if (overviewResult.status === "fulfilled") setOverview(overviewResult.value);
    if (healthResult.status === "fulfilled") setHealth(healthResult.value);
    if (overviewResult.status === "rejected" && healthResult.status === "rejected") setError("账号不存在，或当前 workspace 无权访问该账号。");
    setLoading(false);
  }, [id, scope.workspaceId]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!id || tab !== "content") return;
    let active = true;
    setContentLoading(true);
    void api.accountContent(id, contentDays, scope.workspaceId)
      .then((result) => { if (active) setContent(result); })
      .catch(() => { if (active) setContent(null); })
      .finally(() => { if (active) setContentLoading(false); });
    return () => { active = false; };
  }, [contentDays, id, scope.workspaceId, tab]);

  const updateEvent = async (event: Record<string, unknown>, status: string) => {
    if (!id) return;
    setUpdatingEvent(String(event.id));
    try {
      await api.updateHealthEvent({
        workspace_id: scope.workspaceId,
        account_id: id,
        rule_code: event.rule_code,
        status,
        owner_id: "operator",
      });
      await load();
    } finally {
      setUpdatingEvent("");
    }
  };

  const header = (overview?.header ?? {}) as Record<string, unknown>;
  const kpis = (overview?.kpis ?? {}) as Record<string, { value?: unknown; caveat?: string }>;
  const statuses = (health?.statuses ?? {}) as Record<string, unknown>;
  const events = (health?.events ?? []) as Array<Record<string, unknown>>;
  const growth = (overview?.growth ?? []) as Array<Record<string, unknown>>;
  const organic = (overview?.organic_series ?? []) as Array<Record<string, unknown>>;
  const connection = (health?.connection ?? {}) as Record<string, unknown>;
  const capabilityItems = (((overview?.capabilities ?? {}) as Record<string, unknown>).items ?? []) as Array<Record<string, unknown>>;
  const contentRows = (content?.rows ?? []) as Array<Record<string, unknown>>;
  const contentSummary = (content?.summary ?? {}) as Record<string, unknown>;
  const contentTypes = useMemo(
    () => Array.from(new Set(contentRows.map((row) => String(row.content_type || "UNKNOWN")))),
    [contentRows],
  );
  const visibleContent = useMemo(() => {
    const filtered = contentType === "ALL" ? contentRows : contentRows.filter((row) => String(row.content_type || "UNKNOWN") === contentType);
    return [...filtered].sort((a, b) => {
      if (contentSort === "latest") return new Date(String(b.published_at || 0)).getTime() - new Date(String(a.published_at || 0)).getTime();
      if (contentSort === "engagement") return Number(engagementRate(b) || 0) - Number(engagementRate(a) || 0);
      if (contentSort === "follows") return Number(b.follows || 0) - Number(a.follows || 0);
      return Number(b.organic_views || 0) - Number(a.organic_views || 0);
    });
  }, [contentRows, contentSort, contentType]);

  if (loading && !overview && !health) return <Spinner />;
  if (error && !overview && !health) return <ErrorState message={error} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/accounts" className="text-xs text-slate-500 hover:text-slate-300">← 返回账号中心</Link>
        <div className="flex gap-2">
          <button onClick={() => id && setScope({ accountIds: [id] })} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300">设为当前范围</button>
          <Link to="/reviews" className="rounded-lg bg-sky-500 px-4 py-2 text-xs font-medium text-white">复盘该账号</Link>
        </div>
      </div>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-slate-800 text-lg font-semibold text-slate-200">{String(health?.username ?? header.username ?? "?").slice(0, 1).toUpperCase()}</div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2"><h1 className="truncate text-2xl font-semibold text-slate-100">@{String(health?.username ?? header.username ?? "未知账号")}</h1><HealthStatusBadge value={statuses.overall} /></div>
              <p className="mt-1 text-xs text-slate-500">{String(health?.platform ?? header.platform ?? "UNKNOWN")} · {String(health?.account_type ?? header.account_type ?? "UNKNOWN")} · 最近同步 {formatDate(health?.last_sync_at)}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[["连接", statuses.connection], ["数据", statuses.data], ["经营", statuses.performance], ["内容", statuses.content]].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-slate-800 bg-slate-950/30 px-3 py-2"><p className="mb-1 text-[9px] text-slate-600">{String(label)}</p><HealthStatusBadge value={value} compact /></div>)}
          </div>
        </div>
        <div className={`mt-5 rounded-xl border px-4 py-3 ${health?.data_usable ? "border-emerald-500/20 bg-emerald-500/5" : "border-amber-500/20 bg-amber-500/5"}`}>
          <p className={`text-xs ${health?.data_usable ? "text-emerald-400" : "text-amber-400"}`}>{health?.data_usable ? "该账号数据可用于复盘，但仍需遵守指标口径。" : "该账号数据当前不可用于确定经营判断，请先处理检测异常。"}</p>
        </div>
      </section>

      <div className="overflow-x-auto border-b border-slate-800">
        <div className="flex min-w-max gap-1">
          {TABS.map((item) => <button key={item.key} onClick={() => setTab(item.key)} className={`border-b-2 px-2.5 py-3 text-xs sm:px-4 sm:text-sm ${tab === item.key ? "border-sky-400 text-sky-400" : "border-transparent text-slate-500 hover:text-slate-300"}`}>{item.label}{item.key === "events" && events.length ? ` (${events.length})` : ""}</button>)}
        </div>
      </div>

      {tab === "overview" ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-7">
            {[
              ["当前关注", header.followers, "count", "当前存量，不跨账号去重"],
              ["自然浏览", kpis.views?.value, "count", kpis.views?.caveat],
              ["互动事件", kpis.engagements?.value, "count", "点赞与评论事件之和"],
              ["发布内容", kpis.content_count?.value, "count", "近 30 天"],
              ["广告花费", kpis.paid_spend?.value, "money", "平台报告"],
              ["平台收入", kpis.paid_revenue?.value, "money", "平台归因"],
              ["平台 ROAS", kpis.paid_roas?.value, "ratio", kpis.paid_roas?.caveat],
            ].map(([label, value, type, caveat]) => <div key={String(label)} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-[10px] text-slate-500">{String(label)}</p><p className="mt-2 text-xl font-semibold text-slate-100">{valueText(value, type as "count" | "money" | "ratio")}</p><p className="mt-1 line-clamp-2 text-[9px] leading-relaxed text-slate-600">{String(caveat ?? "")}</p></div>)}
          </div>
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><h2 className="mb-4 text-sm font-semibold text-slate-200">关注趋势</h2><TimeSeriesChart dimensions={["date", "followers"]} rows={growth} metrics={[{ key: "followers", name: "关注", color: "#a78bfa", area: true }]} /></section>
            <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><h2 className="mb-4 text-sm font-semibold text-slate-200">自然表现趋势</h2><TimeSeriesChart dimensions={["date", "views", "engagements"]} rows={organic.map((row) => ({ ...row, engagements: Number(row.likes || 0) + Number(row.comments || 0) }))} metrics={[{ key: "views", name: "浏览", color: "#38bdf8", area: true }, { key: "engagements", name: "互动", color: "#34d399" }]} /></section>
          </div>
        </div>
      ) : null}

      {tab === "events" ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60">
          <div className="border-b border-slate-800 px-5 py-4"><h2 className="text-sm font-semibold text-slate-200">当前检测记录</h2><p className="mt-1 text-xs text-slate-500">每条记录保留规则、观测值和处理建议。</p></div>
          <div className="divide-y divide-slate-800">
            {events.map((event) => <div key={String(event.id)} className="flex flex-col items-start gap-3 px-5 py-4 sm:grid sm:grid-cols-[auto_minmax(0,1fr)_minmax(190px,0.5fr)]"><HealthStatusBadge value={event.severity} compact /><div><p className="text-sm font-medium text-slate-200">{String(event.title)}</p><p className="mt-1 text-xs leading-relaxed text-slate-500">{String(event.detail)}</p><p className="mt-2 text-[10px] text-slate-600">规则 {String(event.rule_code)} · 观测值 {event.observed_value == null ? "无" : String(event.observed_value)}</p></div><div className="w-full space-y-2 sm:w-auto"><div className="rounded-lg border border-slate-800 bg-slate-950/30 p-3 text-xs leading-relaxed text-slate-400">{String(event.action)}</div><select disabled={updatingEvent === String(event.id)} value={String(event.workflow_status ?? "OPEN")} onChange={(change) => void updateEvent(event, change.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-300"><option value="OPEN">待处理</option><option value="IN_PROGRESS">处理中</option><option value="RESOLVED">已解决</option><option value="IGNORED">忽略</option></select>{event.owner_id ? <p className="text-[10px] text-slate-600">负责人：{String(event.owner_id)}</p> : null}</div></div>)}
            {events.length === 0 ? <p className="px-5 py-12 text-center text-sm text-slate-500">当前没有触发检测规则</p> : null}
          </div>
        </section>
      ) : null}

      {tab === "data" ? (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]">
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><h2 className="text-sm font-semibold text-slate-200">账号复盘摘要</h2><p className="mt-3 text-sm leading-relaxed text-slate-400">当前页面保留平台报告表现。第一方净收入、订单和 blended ROAS 请进入数据复盘，与平台归因指标分开核对。</p><Link to="/reviews" className="mt-4 inline-flex rounded-lg bg-sky-500 px-4 py-2 text-xs font-medium text-white">进入数据复盘</Link></section>
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><h2 className="text-sm font-semibold text-slate-200">数据边界</h2><ul className="mt-3 space-y-2 text-xs leading-relaxed text-slate-500"><li>• Views 为平台事件合计，不是唯一观看人数。</li><li>• 当前关注为存量，不与新增关注混用。</li><li>• 平台 ROAS 不等于 Shopify 净收入 ROAS。</li></ul></section>
        </div>
      ) : null}

      {tab === "content" ? (
        <div className="space-y-5">
          <div className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-200">视频表现明细</h2>
              <p className="mt-1 text-xs text-slate-500">逐条查看播放、触达、互动、转粉和投放结果。指标按所选观测窗口累计。</p>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <label className="text-[10px] text-slate-500">数据窗口<select value={contentDays} onChange={(event) => setContentDays(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-300"><option value={7}>近 7 天</option><option value={30}>近 30 天</option><option value={90}>近 90 天</option></select></label>
              <label className="text-[10px] text-slate-500">内容类型<select value={contentType} onChange={(event) => setContentType(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-300"><option value="ALL">全部类型</option>{contentTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
              <label className="text-[10px] text-slate-500">排序<select value={contentSort} onChange={(event) => setContentSort(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-300"><option value="views">播放量</option><option value="engagement">互动率</option><option value="follows">新增关注</option><option value="latest">发布时间</option></select></label>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {[["视频数量", content?.total, "count"], ["总播放", contentSummary.views, "count"], ["总互动", contentSummary.interactions, "count"], ["平均播放", contentSummary.average_views, "count"], ["内容带来关注", contentSummary.follows, "count"]].map(([label, value, type]) => <div key={String(label)} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-[10px] text-slate-500">{String(label)}</p><p className="mt-2 text-xl font-semibold text-slate-100">{contentLoading ? "…" : valueText(value, type as "count")}</p></div>)}
          </div>

          <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
            <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3 sm:px-5"><p className="text-xs text-slate-400">共 {visibleContent.length} 条内容</p><p className="text-[10px] text-slate-600">点击视频查看完整指标与每日趋势</p></div>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[1040px] text-left text-xs">
                <thead className="bg-slate-950/40 text-[10px] uppercase tracking-wide text-slate-600"><tr><th className="px-5 py-3 font-medium">视频</th><th className="px-3 py-3 font-medium">播放 / 触达</th><th className="px-3 py-3 font-medium">互动明细</th><th className="px-3 py-3 font-medium">互动率</th><th className="px-3 py-3 font-medium">转粉</th><th className="px-3 py-3 font-medium">完播 / 跳出</th><th className="px-3 py-3 font-medium">付费</th><th className="px-5 py-3 text-right font-medium">操作</th></tr></thead>
                <tbody className="divide-y divide-slate-800">
                  {visibleContent.map((row) => <tr key={String(row.id)} className="text-slate-400 hover:bg-slate-800/20"><td className="max-w-[280px] px-5 py-4"><p className="line-clamp-2 font-medium text-slate-200">{String(row.caption || "无标题内容")}</p><p className="mt-1 text-[10px] text-slate-600">{String(row.content_type)} · {formatDate(row.published_at)}</p></td><td className="px-3 py-4 tabular-nums"><p className="font-medium text-slate-200">{valueText(row.organic_views)}</p><p className="mt-1 text-[10px] text-slate-600">触达 {valueText(row.reach)}</p></td><td className="px-3 py-4 tabular-nums"><p>{valueText(row.likes)} 赞 · {valueText(row.comments)} 评</p><p className="mt-1 text-[10px] text-slate-600">{valueText(row.shares)} 分享 · {valueText(row.saves)} 收藏</p></td><td className="px-3 py-4 tabular-nums text-slate-200">{percentText(engagementRate(row))}</td><td className="px-3 py-4 tabular-nums text-slate-200">{valueText(row.follows)}</td><td className="px-3 py-4 tabular-nums"><p>{percentText(row.completion_rate)}</p><p className="mt-1 text-[10px] text-slate-600">跳出 {percentText(row.skip_rate)}</p></td><td className="px-3 py-4 tabular-nums"><p>{valueText(row.paid_spend, "money")}</p><p className="mt-1 text-[10px] text-slate-600">ROAS {valueText(row.paid_roas, "ratio")}</p></td><td className="px-5 py-4 text-right"><Link to={`/content/publications/${String(row.id)}`} className="whitespace-nowrap text-sky-400 hover:text-sky-300">查看详情 →</Link></td></tr>)}
                </tbody>
              </table>
            </div>
            <div className="divide-y divide-slate-800 md:hidden">
              {visibleContent.map((row) => <Link to={`/content/publications/${String(row.id)}`} key={String(row.id)} className="block p-4 hover:bg-slate-800/20"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="line-clamp-2 text-sm font-medium text-slate-200">{String(row.caption || "无标题内容")}</p><p className="mt-1 text-[10px] text-slate-600">{String(row.content_type)} · {formatDate(row.published_at)}</p></div><span className="shrink-0 text-xs text-sky-400">详情 →</span></div><div className="mt-4 grid grid-cols-3 gap-3"><div><p className="text-[9px] text-slate-600">播放</p><p className="mt-1 text-sm font-medium text-slate-200">{valueText(row.organic_views)}</p></div><div><p className="text-[9px] text-slate-600">总互动</p><p className="mt-1 text-sm font-medium text-slate-200">{valueText(["likes", "comments", "shares", "saves"].reduce((sum, key) => sum + Number(row[key] || 0), 0))}</p></div><div><p className="text-[9px] text-slate-600">新增关注</p><p className="mt-1 text-sm font-medium text-slate-200">{valueText(row.follows)}</p></div></div><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-500"><span>触达 {valueText(row.reach)}</span><span>互动率 {percentText(engagementRate(row))}</span><span>完播 {percentText(row.completion_rate)}</span><span>花费 {valueText(row.paid_spend, "money")}</span></div></Link>)}
            </div>
            {!contentLoading && visibleContent.length === 0 ? <p className="px-5 py-12 text-center text-sm text-slate-500">当前筛选下没有内容记录。</p> : null}
            {contentLoading ? <p className="px-5 py-12 text-center text-sm text-slate-500">正在加载视频数据…</p> : null}
          </section>
          <p className="px-1 text-[10px] leading-relaxed text-slate-600">数据说明：播放与互动为平台报告事件，不代表去重人数；互动率 =（点赞 + 评论 + 分享 + 收藏）÷ 播放。平台不支持的指标显示为“—”。</p>
        </div>
      ) : null}

      {tab === "connection" ? (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-slate-200">Provider 连接</h2><HealthStatusBadge value={statuses.connection} /></div><dl className="mt-5 grid grid-cols-[130px_minmax(0,1fr)] gap-y-3 text-xs"><dt className="text-slate-600">连接 ID</dt><dd className="break-all text-slate-300">{String(connection.id ?? "未映射")}</dd><dt className="text-slate-600">Provider 状态</dt><dd className="text-slate-300">{String(connection.provider_status ?? "UNKNOWN")}</dd><dt className="text-slate-600">最近验证</dt><dd className="text-slate-300">{formatDate(connection.last_validated_at)}</dd><dt className="text-slate-600">Token 过期</dt><dd className="text-slate-300">{formatDate(connection.token_expires_at)}</dd></dl><p className="mt-5 rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-2 text-[10px] leading-relaxed text-slate-600">这里只显示连接状态和安全引用，不展示 token 或密钥原文。</p></section>
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><div className="flex items-center justify-between gap-3"><div><h2 className="text-sm font-semibold text-slate-200">账号 API 能力</h2><p className="mt-1 text-xs text-slate-500">能力与权限来自账号级探测结果。</p></div><span className="text-[10px] text-slate-600">{capabilityItems.length} 项</span></div><div className="mt-4 space-y-2">{capabilityItems.slice(0, 8).map((item) => { const supported = Boolean(item.supported); const granted = Boolean(item.permission_granted); const label = !supported ? "不支持" : granted ? "已授权" : "未授权"; const tone = !supported ? "UNKNOWN" : granted ? "HEALTHY" : "WARNING"; return <div key={String(item.capability_key)} className="flex items-start justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-2"><div className="min-w-0"><p className="truncate text-xs text-slate-300">{String(item.capability_key)}</p><p className="mt-1 line-clamp-1 text-[10px] text-slate-600">{String(item.limitations ?? (item.last_verified_at ? `最近验证 ${formatDate(item.last_verified_at)}` : "尚未验证"))}</p></div><div className="flex shrink-0 items-center gap-2"><HealthStatusBadge value={tone} compact /><span className="text-[10px] text-slate-400">{label}</span></div></div>; })}{!capabilityItems.length ? <p className="rounded-lg border border-dashed border-slate-700 px-3 py-6 text-center text-xs text-slate-500">账号能力尚未探测</p> : null}</div><p className="mt-4 text-[10px] leading-relaxed text-slate-600">权限由 Provider 返回；这里不伪造前端开关，变更请走连接授权流程。</p></section>
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 xl:col-span-2"><h2 className="text-sm font-semibold text-slate-200">授权范围</h2><div className="mt-4 flex flex-wrap gap-2">{((connection.authorized_scopes ?? []) as unknown[]).map((scopeItem) => <span key={String(scopeItem)} className="rounded-full border border-slate-700 bg-slate-950/40 px-2.5 py-1 text-[10px] text-slate-400">{String(scopeItem)}</span>)}{!((connection.authorized_scopes ?? []) as unknown[]).length ? <span className="text-xs text-slate-500">尚未返回授权 scope</span> : null}</div><Link to="/settings/connections" className="mt-5 inline-flex min-h-10 items-center text-xs text-sky-400">管理连接与授权 →</Link></section>
        </div>
      ) : null}
    </div>
  );
}
