import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { DataBoundaryBanner } from "../components/common/DataBoundaryBanner";
import { ErrorState } from "../components/common/ErrorState";
import { ChartFrame } from "../components/charts/v2/ChartFrame";
import { HorizontalBarChart } from "../components/charts/v2/HorizontalBarChart";
import { TimeSeriesChart } from "../components/charts/v2/TimeSeriesChart";
import { Spinner } from "../components/Spinner";
import { StatusBadge } from "../components/status/StatusBadge";
import { useScope } from "../domain/scope";
import type { CampaignRow } from "../domain/types";

type DataRecord = Record<string, unknown>;

function number(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function money(value: unknown) {
  const parsed = number(value);
  return parsed == null ? "—" : `$${parsed.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function integer(value: unknown) {
  const parsed = number(value);
  return parsed == null ? "—" : parsed.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function ratio(value: unknown) {
  const parsed = number(value);
  return parsed == null ? "—" : `${parsed.toFixed(2)}×`;
}

function metricValue(kpis: DataRecord[], key: string) {
  const row = kpis.find((item) => String(item.key) === key);
  return row?.value;
}

function chartStatus(rows: unknown[], loading: boolean, failed: boolean): "loading" | "ready" | "empty" | "error" {
  if (loading) return "loading";
  if (failed) return "error";
  return rows.length ? "ready" : "empty";
}

export function Ads() {
  const { scope, setScope } = useScope();
  const [campaigns, setCampaigns] = useState<CampaignRow[]>([]);
  const [dashboard, setDashboard] = useState<DataRecord | null>(null);
  const [health, setHealth] = useState<DataRecord | null>(null);
  const initialPaidPlatform = ["META_ADS", "GOOGLE_ADS"].includes(scope.platforms[0] ?? "") ? scope.platforms[0] ?? "" : "";
  const [platform, setPlatform] = useState(initialPaidPlatform);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const [dashboardResult, campaignResult, healthResult] = await Promise.allSettled([
      api.dashboardOverview(),
      api.adsCampaigns(platform || undefined),
      api.healthSummary(scope.workspaceId),
    ]);
    if (dashboardResult.status === "fulfilled") setDashboard(dashboardResult.value);
    if (campaignResult.status === "fulfilled") setCampaigns(campaignResult.value as unknown as CampaignRow[]);
    if (healthResult.status === "fulfilled") setHealth(healthResult.value);
    if (dashboardResult.status === "rejected" && campaignResult.status === "rejected") setError("投放数据加载失败，请检查连接和后端状态。");
    setLoading(false);
  }, [platform, scope.workspaceId]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const nextPlatform = ["META_ADS", "GOOGLE_ADS"].includes(scope.platforms[0] ?? "") ? scope.platforms[0] ?? "" : "";
    if (nextPlatform !== platform) setPlatform(nextPlatform);
  }, [platform, scope.platforms]);

  const kpis = (dashboard?.kpis ?? []) as DataRecord[];
  const trend = (dashboard?.trend ?? []) as DataRecord[];
  const platforms = (dashboard?.platforms ?? []) as DataRecord[];
  const campaignRows = useMemo(() => [...campaigns].sort((a, b) => b.spend - a.spend), [campaigns]);
  const campaignChartRows = useMemo(
    () => campaignRows.slice(0, 8).map((row) => ({ label: row.name, value: row.spend, id: row.campaign_id })),
    [campaignRows],
  );
  const platformChartRows = useMemo(
    () => platforms.map((row) => ({ label: String(row.platform ?? "未知平台"), value: number(row.spend) ?? 0 })),
    [platforms],
  );
  const paidAvailable = platforms.length > 0 || campaignRows.length > 0 || trend.some((row) => (number(row.spend) ?? 0) > 0);
  const commerceAvailable = (number(metricValue(kpis, "orders")) ?? 0) > 0 || trend.some((row) => (number(row.net_revenue) ?? 0) > 0);
  const trendRows = paidAvailable || commerceAvailable ? trend : [];
  const displayMetric = (key: string, formatter: (value: unknown) => string) => {
    const available = key === "paid_spend" || key === "blended_roas" ? paidAvailable : commerceAvailable;
    return available ? formatter(metricValue(kpis, key)) : "—";
  };

  if (loading && !dashboard && !campaigns.length) return <Spinner />;

  return (
    <div className="space-y-5 pb-8 sm:space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-sky-400">Paid media & conversion</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">投放与转化</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">先看花费、收入和转化趋势，再下钻到 Campaign；无可用数据时保留空态和来源边界，不用零值填充。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={platform} onChange={(event) => { const value = event.target.value; setPlatform(value); setScope({ platforms: value ? [value] : [] }); }} aria-label="投放平台" className="min-h-10 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-300"><option value="">全部平台</option><option value="META_ADS">Meta Ads</option><option value="GOOGLE_ADS">Google Ads</option></select>
          <button type="button" onClick={() => void load()} className="min-h-10 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:border-sky-500 hover:text-sky-300">重新读取</button>
          <Link to="/funnel" className="inline-flex min-h-10 items-center rounded-lg bg-sky-500 px-4 py-2 text-xs font-medium text-white transition hover:bg-sky-400">查看转化漏斗</Link>
        </div>
      </header>

      {error ? <ErrorState message={error} /> : null}
      <DataBoundaryBanner dataMode={health?.data_mode} dataUsable={health ? Boolean(health.data_usable) : undefined} evaluatedAt={health?.evaluated_at} blockingReasons={(health?.blocking_reasons ?? []) as unknown[]} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["广告花费", displayMetric("paid_spend", money), "workspace dashboard"],
          ["净收入", displayMetric("net_revenue", money), "FIRST_PARTY / commerce"],
          ["订单数", displayMetric("orders", integer), "FIRST_PARTY / orders"],
          ["混合 ROAS", displayMetric("blended_roas", ratio), "净收入 ÷ 广告花费"],
        ].map(([label, value, hint]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5"><p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">{value}</p><p className="mt-1 text-[10px] leading-relaxed text-slate-600">{hint}</p></div>)}
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(300px,0.85fr)]">
        <ChartFrame title="花费与收入趋势" subtitle="按 workspace 的日粒度汇总；没有已同步记录时明确显示空态。" quality={{ status: chartStatus(trendRows, loading, false), source: "DashboardService.trend", caveat: "净收入与广告花费来自不同数据源，不能当作平台归因。" }}>
          <TimeSeriesChart dimensions={["date"]} rows={trendRows} metrics={[{ key: "spend", name: "广告花费", color: "#f59e0b", area: true }, { key: "net_revenue", name: "净收入", color: "#22c55e" }]} dataZoom={false} height="h-72" ariaLabel="广告花费与净收入趋势" />
        </ChartFrame>
        <ChartFrame title="平台花费贡献" subtitle="观察口径，不代表去重归因。" quality={{ status: chartStatus(platformChartRows, loading, false), source: "MetricsService.platforms", caveat: "平台花费为平台报告值。" }}>
          <HorizontalBarChart rows={platformChartRows} color="#38bdf8" height="h-72" ariaLabel="平台花费贡献" />
        </ChartFrame>
      </div>

      <ChartFrame title="Campaign 花费排行" subtitle={platform ? `当前筛选：${platform}` : "当前 workspace 的可读取 Campaign"} quality={{ status: chartStatus(campaignChartRows, loading, false), source: "AdPerformanceDaily + Campaign", caveat: "仅显示已有 Campaign 主数据和日表现记录的对象。" }}>
        <HorizontalBarChart rows={campaignChartRows} color="#818cf8" height="h-80" ariaLabel="Campaign 花费排行" />
      </ChartFrame>

      <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
        <div className="flex flex-col gap-2 border-b border-slate-800 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"><div><h2 className="text-sm font-semibold text-slate-200">Campaign 明细</h2><p className="mt-1 text-xs text-slate-500">点击进入对象详情，查看规则结果与证据。</p></div><span className="text-[10px] text-slate-600">{campaignRows.length} 个对象</span></div>
        {campaignRows.length ? <div className="overflow-x-auto"><table className="w-full min-w-[980px] text-left text-xs"><thead className="bg-slate-950/30 text-[10px] uppercase tracking-wide text-slate-600"><tr><th className="px-5 py-3 font-medium">名称</th><th className="px-3 py-3 font-medium">平台</th><th className="px-3 py-3 font-medium">状态</th><th className="px-3 py-3 font-medium">花费</th><th className="px-3 py-3 font-medium">展示</th><th className="px-3 py-3 font-medium">点击</th><th className="px-3 py-3 font-medium">转化</th><th className="px-3 py-3 font-medium">CPA</th><th className="px-3 py-3 font-medium">平台 ROAS</th><th className="px-5 py-3 text-right font-medium">规则</th></tr></thead><tbody className="divide-y divide-slate-800">{campaignRows.map((campaign) => <tr key={campaign.id} className="text-slate-400 hover:bg-slate-800/20"><td className="max-w-[260px] px-5 py-4"><Link to={`/ads/campaigns/${campaign.campaign_id}`} className="line-clamp-2 font-medium text-slate-200 hover:text-sky-300">{campaign.name}</Link></td><td className="px-3 py-4">{campaign.platform}</td><td className="px-3 py-4"><StatusBadge value={campaign.status ?? "UNKNOWN"} /></td><td className="px-3 py-4 tabular-nums text-slate-200">{money(campaign.spend)}</td><td className="px-3 py-4 tabular-nums">{integer(campaign.impressions)}</td><td className="px-3 py-4 tabular-nums">{integer(campaign.clicks)}</td><td className="px-3 py-4 tabular-nums text-slate-200">{integer(campaign.conversions)}</td><td className="px-3 py-4 tabular-nums">{money(campaign.cpa)}</td><td className="px-3 py-4 tabular-nums">{ratio(campaign.platform_roas)}</td><td className="px-5 py-4 text-right"><StatusBadge value={campaign.rule_result ?? "UNKNOWN"} /></td></tr>)}</tbody></table></div> : <div className="px-5 py-14 text-center"><p className="text-sm font-medium text-slate-300">当前范围没有可读取的 Campaign</p><p className="mt-1 text-xs leading-relaxed text-slate-500">这不是 0 花费：需要先连接广告数据源并完成同步，系统才会显示对象级数据。</p><Link to="/settings/connections" className="mt-4 inline-flex min-h-10 items-center text-xs text-sky-400">检查连接与同步 →</Link></div>}
      </section>
    </div>
  );
}
