import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ChartFrame } from "../components/charts/v2/ChartFrame";
import { HorizontalBarChart } from "../components/charts/v2/HorizontalBarChart";
import { ScatterMatrixChart } from "../components/charts/v2/ScatterMatrixChart";
import { TimeSeriesChart } from "../components/charts/v2/TimeSeriesChart";
import type { ChartQuality, ChartStatus } from "../components/charts/v2/chartTypes";
import { useScope } from "../domain/scope";

type DataRecord = Record<string, unknown>;
type View = "performance" | "matrix" | "library";

const DAYS_BY_RANGE: Record<string, number> = {
  YESTERDAY: 1,
  LAST_7_DAYS: 7,
  LAST_30_DAYS: 30,
  THIS_MONTH: 30,
  LAST_90_DAYS: 90,
};

const QUADRANT_LABELS: Record<string, { label: string; tone: string }> = {
  SCALE_STAR: { label: "自然与付费双强", tone: "text-emerald-400" },
  HIDDEN_PAID_WINNER: { label: "付费潜力内容", tone: "text-sky-400" },
  ATTENTION_WINNER: { label: "自然表现突出", tone: "text-amber-400" },
  RETIRE_OR_REVIEW: { label: "待复盘", tone: "text-slate-400" },
};

function asRows(value: unknown): DataRecord[] {
  return Array.isArray(value) ? value.filter((row): row is DataRecord => Boolean(row && typeof row === "object")) : [];
}

function asText(value: unknown, fallback = "") {
  return value === null || value === undefined ? fallback : String(value);
}

function asNumber(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function formatDate(value: unknown) {
  if (!value) return "未记录";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "未记录";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit" }).format(date);
}

function formatRange(days: number) {
  if (days === 1) return "昨天";
  return `近 ${days} 天`;
}

function qualityFrom(value: unknown, fallbackStatus: ChartStatus): ChartQuality {
  const raw = value && typeof value === "object" ? value as DataRecord : {};
  const allowed: ChartStatus[] = ["ready", "loading", "empty", "partial", "stale", "not_connected", "error"];
  const status = allowed.includes(asText(raw.status) as ChartStatus) ? asText(raw.status) as ChartStatus : fallbackStatus;
  const sampleSize = raw.sample_size === null || raw.sample_size === undefined ? null : asNumber(raw.sample_size);
  return {
    status,
    source: raw.source ? asText(raw.source) : undefined,
    freshness: raw.freshness ? asText(raw.freshness) : null,
    completeness: raw.completeness === null || raw.completeness === undefined ? null : asNumber(raw.completeness),
    sampleSize,
    comparableSampleSize: raw.comparable_sample_size === null || raw.comparable_sample_size === undefined ? null : asNumber(raw.comparable_sample_size),
    caveat: raw.caveat ? asText(raw.caveat) : null,
    error: raw.error ? asText(raw.error) : null,
  };
}

function withRuntimeStatus(quality: ChartQuality, loading: boolean, error: string, hasData: boolean): ChartQuality {
  if (loading) return { ...quality, status: "loading" };
  if (error) return { ...quality, status: "error", error };
  if (!hasData && quality.status === "ready") return { ...quality, status: "empty" };
  return quality;
}

function median(values: number[]) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">{value}</p>
      <p className="mt-1 text-[10px] leading-relaxed text-slate-600">{hint}</p>
    </div>
  );
}

function DataQualityPanel({ trendDays, contentCount, comparableCount, source }: { trendDays: number; contentCount: number; comparableCount: number; source?: string }) {
  const comparableReady = comparableCount >= 8;
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">当前数据检查</h2>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">先确认样本是否足够，再决定是否进入复核或投放动作。</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-[10px] ${comparableReady ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"}`}>{comparableReady ? "可比较" : "需补数据"}</span>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-2">
        <div className="rounded-lg border border-slate-800 bg-slate-950/30 p-3"><dt className="text-[10px] text-slate-600">自然日期</dt><dd className="mt-1 text-sm font-semibold tabular-nums text-slate-200">{trendDays} 天</dd></div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/30 p-3"><dt className="text-[10px] text-slate-600">发布记录</dt><dd className="mt-1 text-sm font-semibold tabular-nums text-slate-200">{contentCount}</dd></div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/30 p-3"><dt className="text-[10px] text-slate-600">付费可比</dt><dd className="mt-1 text-sm font-semibold tabular-nums text-slate-200">{comparableCount}</dd></div>
      </dl>
      <p className="mt-3 text-[10px] leading-relaxed text-slate-600">{comparableReady ? "自然与付费结果达到矩阵复核阈值。" : "当前付费结果不足，系统不会把缺失付费数据当作有效的 0。"}{source ? ` 来源：${source}` : ""}</p>
    </section>
  );
}

function ContentTable({ rows, accountMap, matrixMap }: { rows: DataRecord[]; accountMap: Map<string, DataRecord>; matrixMap: Map<string, DataRecord> }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
      <div className="border-b border-slate-800 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">内容表现排行</h2>
            <p className="mt-1 text-xs text-slate-500">按自然浏览排序；付费花费和付费判断保持独立。</p>
          </div>
          <span className="text-[10px] text-slate-600">点击内容进入复核维度</span>
        </div>
      </div>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[820px] text-left text-xs" aria-label="内容表现排行">
          <thead className="bg-slate-950/30 text-slate-500">
            <tr>
              <th className="px-5 py-3 font-medium">内容</th>
              <th className="font-medium">账号</th>
              <th className="font-medium">发布时间</th>
              <th className="font-medium">自然浏览</th>
              <th className="font-medium">付费花费</th>
              <th className="font-medium">判断</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {rows.map((row) => {
              const id = asText(row.id);
              const account = accountMap.get(asText(row.account_id));
              const matrix = matrixMap.get(id);
              const quadrant = QUADRANT_LABELS[asText(matrix?.quadrant)] ?? QUADRANT_LABELS.RETIRE_OR_REVIEW;
              return (
                <tr key={id} className="text-slate-400 transition hover:bg-slate-800/20">
                  <td className="max-w-sm px-5 py-4">
                    <Link to={`/content/publications/${id}`} className="line-clamp-2 font-medium text-slate-200 hover:text-sky-400">
                      {asText(row.caption, "无标题内容")}
                    </Link>
                    <p className="mt-1 text-[10px] text-slate-600">{asText(row.platform, "未知平台")} · {asText(row.content_type, "未知类型")}</p>
                  </td>
                  <td>@{asText(account?.username, "未知账号")}</td>
                  <td>{formatDate(row.published_at)}</td>
                  <td className="tabular-nums text-slate-200">{asNumber(row.organic_views).toLocaleString("zh-CN")}</td>
                  <td className="tabular-nums">${asNumber(row.paid_spend).toFixed(2)}</td>
                  <td><span className={quadrant.tone}>{quadrant.label}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="divide-y divide-slate-800 md:hidden">
        {rows.map((row) => {
          const id = asText(row.id);
          const matrix = matrixMap.get(id);
          const quadrant = QUADRANT_LABELS[asText(matrix?.quadrant)] ?? QUADRANT_LABELS.RETIRE_OR_REVIEW;
          return (
            <Link key={id} to={`/content/publications/${id}`} className="block p-4 transition hover:bg-slate-800/20">
              <div className="flex items-start justify-between gap-3">
                <p className="line-clamp-2 text-sm font-medium text-slate-200">{asText(row.caption, "无标题内容")}</p>
                <span className={`shrink-0 text-[10px] ${quadrant.tone}`}>{quadrant.label}</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                <span>{asText(row.platform, "未知平台")}</span>
                <span>{asNumber(row.organic_views).toLocaleString("zh-CN")} 浏览</span>
                <span>${asNumber(row.paid_spend).toFixed(2)} 花费</span>
              </div>
            </Link>
          );
        })}
      </div>
      {!rows.length ? <div className="px-5 py-12 text-center text-sm text-slate-500">当前范围暂无内容表现数据。</div> : null}
    </section>
  );
}

export function ContentIntelligence() {
  const { scope, accounts, setScope } = useScope();
  const [contentRows, setContentRows] = useState<DataRecord[]>([]);
  const [trendRows, setTrendRows] = useState<DataRecord[]>([]);
  const [matrixRows, setMatrixRows] = useState<DataRecord[]>([]);
  const [performanceQuality, setPerformanceQuality] = useState<ChartQuality>({ status: "loading" });
  const [matrixQuality, setMatrixQuality] = useState<ChartQuality>({ status: "loading" });
  const [view, setView] = useState<View>("performance");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const accountIds = scope.accountIds.join(",");
  const days = DAYS_BY_RANGE[scope.dateRange] ?? 30;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setPerformanceQuality({ status: "loading" });
    setMatrixQuality({ status: "loading" });
    try {
      const [performanceData, matrixData] = await Promise.all([
        api.portfolioContent(scope.workspaceId, accountIds, days),
        api.portfolioContentMatrix(scope.workspaceId, accountIds, days),
      ]);
      const performanceRows = asRows(performanceData.rows);
      const nextTrendRows = asRows(performanceData.series);
      const nextMatrixRows = asRows(matrixData.rows);
      setContentRows(performanceRows);
      setTrendRows(nextTrendRows);
      setMatrixRows(nextMatrixRows);
      setPerformanceQuality(qualityFrom(performanceData.quality, performanceRows.length || nextTrendRows.length ? "ready" : "empty"));
      setMatrixQuality(qualityFrom(matrixData.quality, nextMatrixRows.length >= 8 ? "ready" : nextMatrixRows.length ? "partial" : "empty"));
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "内容表现加载失败";
      setError(message);
      setPerformanceQuality({ status: "error", error: message });
      setMatrixQuality({ status: "error", error: message });
    } finally {
      setLoading(false);
    }
  }, [accountIds, days, scope.workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const accountMap = useMemo(
    () => new Map(accounts.map((account) => [asText(account.id), account])),
    [accounts],
  );
  const matrixMap = useMemo(
    () => new Map(matrixRows.map((row) => [asText(row.publication_id), row])),
    [matrixRows],
  );
  const rankedRows = useMemo(
    () => [...contentRows].sort((a, b) => asNumber(b.organic_views) - asNumber(a.organic_views)),
    [contentRows],
  );
  const topRows = useMemo(
    () => rankedRows.slice(0, 8).map((row) => ({ label: asText(row.caption, "无标题内容").slice(0, 24), value: asNumber(row.organic_views), id: asText(row.id) })),
    [rankedRows],
  );
  const totalViews = rankedRows.reduce((sum, row) => sum + asNumber(row.organic_views), 0);
  const medianViews = median(rankedRows.map((row) => asNumber(row.organic_views)).filter((value) => value > 0));
  const promotedCount = rankedRows.filter((row) => asNumber(row.paid_spend) > 0).length;
  const attentionCount = matrixRows.filter((row) => asText(row.quadrant) === "ATTENTION_WINNER").length;
  const readyRows = trendRows.length || contentRows.length || matrixRows.length;
  const trendQuality = withRuntimeStatus(performanceQuality, loading, error, trendRows.length > 0);
  const cadenceQuality = withRuntimeStatus(performanceQuality, loading, error, trendRows.length > 0);
  const matrixViewQuality = withRuntimeStatus(matrixQuality, loading, error, matrixRows.length >= 8);
  const libraryQuality = withRuntimeStatus(performanceQuality, loading, error, contentRows.length > 0);

  return (
    <div className="space-y-5 pb-8 sm:space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-sky-400">Content performance</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">内容表现</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">以独立发布记录为单位，先看原始表现，再进入复核维度；自然指标与付费指标不混成一个分数。</p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-xs text-slate-500">{formatRange(days)} · {scope.accountIds.length ? `${scope.accountIds.length} 个账号` : "全部已连接账号"}</span>
          <button type="button" onClick={() => void load()} className="min-h-10 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:border-sky-500 hover:text-sky-300">刷新数据</button>
        </div>
      </header>

      {error ? (
        <div role="alert" className="flex flex-col gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200 sm:flex-row sm:items-center sm:justify-between">
          <span>{error}</span>
          <button type="button" onClick={() => void load()} className="self-start rounded-lg border border-rose-400/30 px-3 py-2 text-xs hover:bg-rose-400/10 sm:self-auto">重试</button>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="发布内容" value={loading && !readyRows ? "—" : rankedRows.length.toLocaleString("zh-CN")} hint={`${new Set(rankedRows.map((row) => asText(row.account_id))).size} 个账号有发布记录`} />
        <Metric label="自然浏览事件" value={loading && !readyRows ? "—" : totalViews.toLocaleString("zh-CN")} hint="平台报告事件合计，不代表去重用户" />
        <Metric label="单条中位浏览" value={loading && !readyRows ? "—" : medianViews.toLocaleString("zh-CN")} hint="避免被单条爆款拉高整体判断" />
        <Metric label="已有付费承接" value={loading && !readyRows ? "—" : promotedCount.toLocaleString("zh-CN")} hint={`${attentionCount} 条自然表现突出，建议复核放大条件`} />
      </div>

      <nav className="flex max-w-full overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/50 p-1" aria-label="内容表现视图">
        {([
          ["performance", "排行与趋势"],
          ["matrix", "表现矩阵"],
          ["library", "内容库"],
        ] as Array<[View, string]>).map(([value, label]) => (
          <button key={value} type="button" onClick={() => setView(value)} className={`min-h-10 shrink-0 rounded-lg px-4 py-2 text-xs transition ${view === value ? "bg-sky-500 text-white" : "text-slate-400 hover:text-slate-200"}`} aria-current={view === value ? "page" : undefined}>{label}</button>
        ))}
      </nav>

      {view === "performance" ? (
        <div className="space-y-4">
          <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
            <ChartFrame title="自然浏览趋势" subtitle="按天汇总当前账号范围的自然浏览事件；缺失日期不会被补成 0。" quality={trendQuality} onRetry={() => void load()}>
              <TimeSeriesChart dimensions={["date"]} rows={trendRows} metrics={[{ key: "views", name: "自然浏览", area: true }]} yAxisName="浏览事件" height="h-72 sm:h-80" ariaLabel="自然浏览趋势折线图" />
            </ChartFrame>
            <ChartFrame title="发布节奏" subtitle="用每日发布数量判断内容供给是否断档，不与浏览量混算。" quality={cadenceQuality} onRetry={() => void load()}>
              <TimeSeriesChart dimensions={["date"]} rows={trendRows} metrics={[{ key: "content_count", name: "发布条数", color: "#a78bfa" }]} yAxisName="条" dataZoom={false} height="h-72 sm:h-80" ariaLabel="每日发布节奏折线图" />
            </ChartFrame>
          </div>
          <div className="grid min-w-0 items-start gap-4 xl:grid-cols-[minmax(280px,0.72fr)_minmax(0,1.28fr)]">
            <div className="space-y-4">
              <ChartFrame title="自然浏览 Top 8" subtitle="用于快速定位值得进入复核的独立发布记录。" quality={withRuntimeStatus(performanceQuality, loading, error, topRows.length > 0)} onRetry={() => void load()}>
                <HorizontalBarChart rows={topRows} height="h-80" ariaLabel="自然浏览最高的八条内容横向排行" />
              </ChartFrame>
              <DataQualityPanel trendDays={trendRows.length} contentCount={contentRows.length} comparableCount={matrixQuality.comparableSampleSize ?? 0} source={performanceQuality.source} />
            </div>
            <ContentTable rows={rankedRows} accountMap={accountMap} matrixMap={matrixMap} />
          </div>
        </div>
      ) : null}

      {view === "matrix" ? (
        <div className="space-y-4">
          <ChartFrame title="自然表现 × 付费效率" subtitle="每个点代表一条独立发布记录；点击内容点会把当前 publication 写入全局范围。少于 8 条内容时仅保留表格复核。" quality={matrixViewQuality} onRetry={() => void load()}>
            <ScatterMatrixChart
              rows={matrixRows.map((row) => ({ ...row, name: asText(row.caption, row.publication_id ? `内容 ${row.publication_id}` : "内容") }))}
              xKey="organic_percentile"
              yKey="paid_percentile"
              xName="自然表现百分位"
              yName="付费效率百分位"
              sizeKey="organic_views"
              visualKey="paid_roas"
              ariaLabel="自然表现与付费效率散点图"
              onEvent={(type, params) => {
                if (type !== "click") return;
                const row = (params as { data?: { row?: DataRecord } }).data?.row;
                if (row?.publication_id) setScope({ publicationId: asText(row.publication_id) });
              }}
            />
          </ChartFrame>
          <div className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2 xl:grid-cols-4">
            {Object.entries(QUADRANT_LABELS).map(([key, value]) => <div key={key} className="rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-3"><span className={value.tone}>{value.label}</span><p className="mt-1 text-[10px] text-slate-600">{key === "SCALE_STAR" ? "自然和付费两侧都在高位" : key === "HIDDEN_PAID_WINNER" ? "付费反馈好，需复核自然分发" : key === "ATTENTION_WINNER" ? "自然信号好，检查放大条件" : "暂不建议直接扩大预算"}</p></div>)}
          </div>
          <ContentTable rows={rankedRows} accountMap={accountMap} matrixMap={matrixMap} />
        </div>
      ) : null}

      {view === "library" ? (
        <div className="space-y-4">
          <ChartFrame title="独立发布记录" subtitle="这里按 publication 展示内容，不假设存在母素材层级；相似场景、产品或 hook 关系后续以标签和关系表补充。" quality={libraryQuality} onRetry={() => void load()}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {rankedRows.map((row) => {
                const id = asText(row.id);
                const account = accountMap.get(asText(row.account_id));
                return (
                  <Link key={id} to={`/content/publications/${id}`} className="min-w-0 rounded-xl border border-slate-800 bg-slate-950/30 p-4 transition hover:border-sky-500/50 hover:bg-slate-900">
                    <div className="flex items-center justify-between gap-3 text-[10px] text-slate-500"><span>{asText(row.platform, "未知平台")}</span><span>{formatDate(row.published_at)}</span></div>
                    <p className="mt-3 line-clamp-3 text-sm font-medium leading-relaxed text-slate-200">{asText(row.caption, "无标题内容")}</p>
                    <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500"><span>@{asText(account?.username, "未知账号")}</span><span>{asNumber(row.organic_views).toLocaleString("zh-CN")} 浏览</span><span>${asNumber(row.paid_spend).toFixed(2)} 付费</span></div>
                  </Link>
                );
              })}
            </div>
            {!rankedRows.length ? <p className="py-10 text-center text-sm text-slate-500">当前范围暂无独立发布记录。</p> : null}
          </ChartFrame>
        </div>
      ) : null}
    </div>
  );
}
