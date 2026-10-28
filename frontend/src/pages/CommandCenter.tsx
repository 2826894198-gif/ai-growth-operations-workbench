import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { TimeSeriesChart } from "../components/charts/v2/TimeSeriesChart";
import { DataBoundaryBanner } from "../components/common/DataBoundaryBanner";
import { ErrorState } from "../components/common/ErrorState";
import { HealthStatusBadge } from "../components/health/HealthStatusBadge";
import { ReviewMetricCard } from "../components/review/ReviewMetricCard";
import { Spinner } from "../components/Spinner";
import { useScope } from "../domain/scope";

const KPI_ORDER = ["net_revenue", "paid_spend", "orders", "blended_roas", "paid_roas"];

function timeAgo(value?: unknown) {
  if (!value) return "未同步";
  const diff = Date.now() - new Date(String(value)).getTime();
  if (!Number.isFinite(diff)) return "未知";
  const minutes = Math.max(0, Math.round(diff / 60000));
  if (minutes < 60) return `${minutes} 分钟前`;
  if (minutes < 1440) return `${Math.round(minutes / 60)} 小时前`;
  return `${Math.round(minutes / 1440)} 天前`;
}

export function CommandCenter() {
  const { scope } = useScope();
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [portfolio, setPortfolio] = useState<Record<string, unknown> | null>(null);
  const [reviews, setReviews] = useState<Array<Record<string, unknown>>>([]);
  const [trend, setTrend] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingEvent, setUpdatingEvent] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const results = await Promise.allSettled([
      api.healthSummary(scope.workspaceId),
      api.reviewPreview(scope.workspaceId, "DAILY", scope.accountIds),
      api.portfolioOverview(scope.workspaceId, scope.platforms.join(","), 30),
      api.reviews(scope.workspaceId),
      api.reviewTrends(scope.workspaceId, 7, scope.accountIds),
    ]);
    if (results[0].status === "fulfilled") setHealth(results[0].value);
    if (results[1].status === "fulfilled") setPreview(results[1].value);
    if (results[2].status === "fulfilled") setPortfolio(results[2].value);
    if (results[3].status === "fulfilled") setReviews(results[3].value);
    if (results[4].status === "fulfilled") setTrend(results[4].value);
    if (results.every((result) => result.status === "rejected")) setError("概览数据加载失败，请检查后端和数据库状态。");
    setLoading(false);
  }, [scope.accountIds, scope.platforms, scope.workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const counts = (health?.counts ?? {}) as Record<string, number>;
  const events = (health?.top_events ?? []) as Array<Record<string, unknown>>;
  const healthAccounts = (health?.accounts ?? []) as Array<Record<string, unknown>>;
  const portfolioAccounts = (portfolio?.accounts ?? []) as Array<Record<string, unknown>>;
  const metrics = (preview?.metrics ?? {}) as Record<string, Record<string, unknown>>;
  const trendRows = (trend?.rows ?? []) as Array<Record<string, unknown>>;
  const findings = (preview?.findings ?? []) as Array<Record<string, unknown>>;

  const updateEvent = async (event: Record<string, unknown>, status: string) => {
    const key = String(event.id);
    setUpdatingEvent(key);
    try {
      await api.updateHealthEvent({
        workspace_id: scope.workspaceId,
        account_id: event.account_id,
        rule_code: event.rule_code,
        status,
        owner_id: "operator",
      });
      await load();
    } finally {
      setUpdatingEvent("");
    }
  };

  const accountRows = useMemo(() => {
    const metricMap = new Map(portfolioAccounts.map((row) => [String(row.id), row]));
    return healthAccounts.map((row) => ({ ...row, ...(metricMap.get(String(row.account_id)) ?? {}) }));
  }, [healthAccounts, portfolioAccounts]);

  if (loading && !health && !preview) return <Spinner />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-sky-400">Daily control room</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">今天先处理什么</h1>
          <p className="mt-1 text-sm text-slate-500">先确认账号和数据是否正常，再看经营变化。</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => void load()} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-slate-600">重新检测</button>
          <Link to="/reviews" className="rounded-lg bg-sky-500 px-4 py-2 text-xs font-medium text-white hover:bg-sky-400">开始今日复盘</Link>
        </div>
      </div>

      {error ? <ErrorState message={error} /> : null}
      <DataBoundaryBanner
        dataMode={health?.data_mode}
        dataUsable={Boolean(health?.data_usable)}
        evaluatedAt={health?.evaluated_at}
        blockingReasons={(health?.blocking_reasons ?? []) as unknown[]}
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.75fr)]">
        <section id="exceptions" className="min-w-0 scroll-mt-24 rounded-2xl border border-slate-800 bg-slate-900/60">
          <div className="flex items-center justify-between border-b border-slate-800 px-4 py-4 sm:px-5">
            <div>
              <h2 className="text-sm font-semibold text-slate-200">优先处理</h2>
              <p className="mt-0.5 text-xs text-slate-500">按严重级别排列的账号与数据异常</p>
            </div>
            <Link to="/accounts" className="text-xs text-sky-400">查看全部账号 →</Link>
          </div>
          <div className="divide-y divide-slate-800/80">
            {events.slice(0, 5).map((event) => (
              <div key={String(event.id)} className="flex flex-col gap-3 px-4 py-4 transition-colors hover:bg-slate-800/30 sm:flex-row sm:items-center sm:px-5">
                <HealthStatusBadge value={event.severity} compact />
                <Link to={`/accounts/${String(event.account_id)}`} className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-200">{String(event.title)}</p>
                  <p className="mt-0.5 truncate text-xs text-slate-500">{String(event.platform)} @{String(event.username)} · {String(event.detail)}</p>
                </Link>
                <select disabled={updatingEvent === String(event.id)} value={String(event.workflow_status ?? "OPEN")} onChange={(change) => void updateEvent(event, change.target.value)} className="self-start rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-[10px] text-slate-300 sm:self-auto"><option value="OPEN">待处理</option><option value="IN_PROGRESS">处理中</option><option value="RESOLVED">已解决</option><option value="IGNORED">忽略</option></select>
              </div>
            ))}
            {events.length === 0 ? (
              <div className="px-5 py-10 text-center">
                <p className="text-sm text-slate-300">当前没有需要立即处理的异常</p>
                <p className="mt-1 text-xs text-slate-600">仍需结合数据新鲜度确认是否可以做经营判断。</p>
              </div>
            ) : null}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-200">账号健康分布</h2>
              <p className="mt-0.5 text-xs text-slate-500">总状态只用于排序</p>
            </div>
            <p className="text-3xl font-semibold text-slate-100">{counts.total_accounts ?? 0}</p>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3">
            {[
              ["critical", "严重", "text-rose-400"],
              ["at_risk", "高风险", "text-orange-400"],
              ["warning", "需观察", "text-amber-400"],
              ["healthy", "正常", "text-emerald-400"],
            ].map(([key, label, tone]) => (
              <div key={key} className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                <p className="text-[10px] text-slate-500">{label}</p>
                <p className={`mt-1 text-2xl font-semibold ${tone}`}>{counts[key] ?? 0}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 border-t border-slate-800 pt-4">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500">状态未知</span>
              <span className="font-medium text-slate-300">{counts.unknown ?? 0}</span>
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-slate-600">未知不会按正常处理。需要先补齐授权、同步或检测能力。</p>
          </div>
        </section>
      </div>

      <section>
        <div className="mb-3 flex items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">昨日经营摘要</h2>
            <p className="mt-0.5 text-xs text-slate-500">第一方指标和平台归因指标分开显示</p>
          </div>
          <HealthStatusBadge value={preview?.data_status} />
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          {KPI_ORDER.map((key) => metrics[key] ? <ReviewMetricCard key={key} metric={metrics[key]} /> : (
            <div key={key} className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-600">指标不可用</div>
          ))}
        </div>
        <div className="mt-3 rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3">
          <p className="text-sm leading-relaxed text-slate-300">{String(preview?.summary ?? "暂无可用复盘结论")}</p>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
        <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
          <div><h2 className="text-sm font-semibold text-slate-200">近7天经营趋势</h2><p className="mt-0.5 text-xs text-slate-500">净收入为第一方口径，广告花费为平台报告口径。</p></div>
          <div className="mt-4"><TimeSeriesChart dimensions={["date", "net_revenue", "paid_spend"]} rows={trendRows} metrics={[{ key: "net_revenue", name: "净收入", color: "#34d399", area: true }, { key: "paid_spend", name: "广告花费", color: "#38bdf8" }]} dataZoom={false} height="h-64" /></div>
        </section>
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
          <h2 className="text-sm font-semibold text-slate-200">变化原因候选</h2>
          <p className="mt-1 text-xs text-slate-500">这里只提示同期变化，最终原因需进入复盘下钻核对。</p>
          <div className="mt-4 space-y-3">{findings.slice(0, 4).map((finding, index) => <div key={`${String(finding.metric_key)}-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/30 p-3"><div className="flex items-start gap-2"><HealthStatusBadge value={finding.severity} compact /><p className="text-xs font-medium leading-relaxed text-slate-300">{String(finding.title)}</p></div><p className="mt-2 text-[10px] leading-relaxed text-slate-600">{String(finding.description)}</p></div>)}{findings.length === 0 ? <p className="py-6 text-center text-xs text-slate-500">当前没有达到变化阈值的指标</p> : null}</div>
          <Link to="/reviews" className="mt-4 inline-flex text-xs text-sky-400">进入完整复盘 →</Link>
        </section>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
        <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-200">账号巡检</h2>
              <p className="mt-0.5 text-xs text-slate-500">连接、数据和经营状态分别展示</p>
            </div>
            <Link to="/accounts" className="text-xs text-sky-400">完整列表 →</Link>
          </div>
          <div className="mt-4 space-y-2">
            {accountRows.slice(0, 6).map((account) => {
              const statuses = (account.statuses ?? {}) as Record<string, unknown>;
              return (
                <Link key={String(account.account_id)} to={`/accounts/${String(account.account_id)}`} className="grid gap-3 rounded-xl border border-slate-800 bg-slate-950/30 p-3 hover:border-slate-700 sm:grid-cols-[minmax(150px,1fr)_repeat(3,auto)_100px] sm:items-center">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-200">@{String(account.username)}</p>
                    <p className="text-[10px] text-slate-500">{String(account.platform)} · {timeAgo(account.last_sync_at)}</p>
                  </div>
                  <div><p className="mb-1 text-[9px] text-slate-600">连接</p><HealthStatusBadge value={statuses.connection} compact /></div>
                  <div><p className="mb-1 text-[9px] text-slate-600">数据</p><HealthStatusBadge value={statuses.data} compact /></div>
                  <div><p className="mb-1 text-[9px] text-slate-600">经营</p><HealthStatusBadge value={statuses.performance} compact /></div>
                  <p className="text-right text-xs text-slate-400">{Number(account.views || 0).toLocaleString()} 浏览</p>
                </Link>
              );
            })}
            {accountRows.length === 0 ? <p className="py-8 text-center text-sm text-slate-500">暂无已连接账号</p> : null}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
          <h2 className="text-sm font-semibold text-slate-200">复盘进度</h2>
          <p className="mt-1 text-xs text-slate-500">完成检测后保存当日结论和跟进项。</p>
          <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
            <p className="text-[10px] uppercase tracking-wider text-slate-600">最近一次复盘</p>
            {reviews[0] ? (
              <>
                <p className="mt-2 text-sm font-medium text-slate-200">{String(reviews[0].review_type)} · {String((reviews[0].period as Record<string, unknown>)?.period_end)}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-500">{String(reviews[0].summary ?? "未填写总结")}</p>
                <Link to={`/reviews/${String(reviews[0].id)}`} className="mt-3 inline-flex text-xs text-sky-400">查看复盘 →</Link>
              </>
            ) : <p className="mt-2 text-sm text-slate-500">尚未保存复盘</p>}
          </div>
          <Link to="/reviews" className="mt-4 flex min-h-10 items-center justify-center rounded-lg bg-sky-500 px-4 text-sm font-medium text-white hover:bg-sky-400">开始复盘</Link>
        </section>
      </div>
    </div>
  );
}
