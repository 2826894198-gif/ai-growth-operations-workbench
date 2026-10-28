import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { ErrorState } from "../components/common/ErrorState";
import { HealthStatusBadge } from "../components/health/HealthStatusBadge";
import { Spinner } from "../components/Spinner";
import { useScope } from "../domain/scope";

interface SourceHealth {
  provider: string;
  name: string;
  status?: string;
  last_successful_sync_at?: string | null;
  last_failed_sync_at?: string | null;
  sync_lag_seconds?: number | null;
}

function dateTime(value: unknown) {
  if (!value) return "未记录";
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
}

function lagText(seconds: unknown) {
  if (seconds == null) return "未知";
  const number = Number(seconds);
  if (number < 60) return `${Math.round(number)} 秒`;
  if (number < 3600) return `${Math.round(number / 60)} 分钟`;
  return `${(number / 3600).toFixed(1)} 小时`;
}

export function DataHealth() {
  const { scope } = useScope();
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [webhooks, setWebhooks] = useState<Record<string, unknown>>({});
  const [issues, setIssues] = useState<{ open_issues: Array<Record<string, unknown>>; total_open: number }>({ open_issues: [], total_open: 0 });
  const [jobs, setJobs] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [freshness, quality, jobData] = await Promise.all([
        api.dataHealthFreshness(scope.workspaceId),
        api.dataHealthQuality(scope.workspaceId),
        api.dataHealthJobs(scope.workspaceId),
      ]);
      setSources(freshness.sources as unknown as SourceHealth[]);
      setWebhooks(freshness.webhooks);
      setIssues(quality);
      setJobs(jobData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "数据健康加载失败");
    } finally {
      setLoading(false);
    }
  }, [scope.workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const counts = useMemo(() => sources.reduce<Record<string, number>>((result, source) => {
    const key = String(source.status || "UNKNOWN");
    result[key] = (result[key] ?? 0) + 1;
    return result;
  }, {}), [sources]);

  if (loading && !sources.length) return <Spinner />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div><p className="text-xs font-medium uppercase tracking-[0.18em] text-sky-400">Data trust center</p><h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">数据健康</h1><p className="mt-1 text-sm text-slate-500">先判断数据是否新鲜、完整和可信，再进入经营复盘。</p></div>
        <button onClick={() => void load()} className="self-start rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300">重新检查</button>
      </div>

      {error ? <ErrorState message={error} /> : null}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {[["FRESH", "新鲜", "text-emerald-400"], ["DELAYED", "延迟", "text-amber-400"], ["STALE", "过期", "text-orange-400"], ["UNKNOWN", "未知", "text-slate-400"], ["ISSUES", "质量问题", "text-rose-400"]].map(([key, label, tone]) => <div key={key} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-[10px] text-slate-500">{label}</p><p className={`mt-1 text-2xl font-semibold ${tone}`}>{key === "ISSUES" ? issues.total_open : counts[key] ?? 0}</p></div>)}
      </div>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/60">
        <div className="border-b border-slate-800 px-5 py-4"><h2 className="text-sm font-semibold text-slate-200">数据源新鲜度</h2><p className="mt-0.5 text-xs text-slate-500">常规目标 20 分钟内；超过 60 分钟视为过期。</p></div>
        <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
          {sources.map((source) => <div key={`${source.provider}-${source.name}`} className="rounded-xl border border-slate-800 bg-slate-950/30 p-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-medium text-slate-200">{source.name}</p><p className="mt-0.5 text-[10px] text-slate-600">{source.provider}</p></div><HealthStatusBadge value={source.status} compact /></div><dl className="mt-4 grid grid-cols-[88px_minmax(0,1fr)] gap-y-2 text-xs"><dt className="text-slate-600">同步延迟</dt><dd className="text-slate-300">{lagText(source.sync_lag_seconds)}</dd><dt className="text-slate-600">最后成功</dt><dd className="text-slate-300">{dateTime(source.last_successful_sync_at)}</dd><dt className="text-slate-600">最后失败</dt><dd className="text-slate-300">{dateTime(source.last_failed_sync_at)}</dd></dl></div>)}
          {sources.length === 0 ? <div className="col-span-full py-10 text-center"><p className="text-sm text-slate-300">当前 workspace 没有数据源</p><p className="mt-1 text-xs text-slate-600">请先连接 Shopify、Meta 或 Google 数据源。</p></div> : null}
        </div>
      </section>

      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.55fr)]">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60">
          <div className="border-b border-slate-800 px-5 py-4"><h2 className="text-sm font-semibold text-slate-200">最近同步任务</h2><p className="mt-0.5 text-xs text-slate-500">任务失败时保留错误，成功时更新数据新鲜度。</p></div>
          <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-left text-xs"><thead className="border-b border-slate-800 uppercase tracking-wider text-slate-600"><tr><th className="px-5 py-3 font-medium">Provider</th><th className="px-3 py-3 font-medium">任务</th><th className="px-3 py-3 font-medium">状态</th><th className="px-3 py-3 font-medium">创建时间</th><th className="px-5 py-3 font-medium">完成时间</th></tr></thead><tbody className="divide-y divide-slate-800/80">{jobs.map((job) => <tr key={String(job.id)}><td className="px-5 py-3 text-slate-300">{String(job.provider)}</td><td className="px-3 py-3 text-slate-500">{String(job.job_type)}</td><td className="px-3 py-3"><HealthStatusBadge value={job.status} compact /></td><td className="px-3 py-3 text-slate-500">{dateTime(job.created_at)}</td><td className="px-5 py-3 text-slate-500">{dateTime(job.finished_at)}</td></tr>)}</tbody></table>{jobs.length === 0 ? <p className="px-5 py-10 text-center text-sm text-slate-500">暂无同步任务</p> : null}</div>
        </section>

        <div className="space-y-6">
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-slate-200">质量问题</h2><span className="text-2xl font-semibold text-rose-400">{issues.total_open}</span></div><div className="mt-4 space-y-2">{issues.open_issues.slice(0, 8).map((issue) => <div key={`${String(issue.rule_code)}-${String(issue.severity)}`} className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-2"><div className="min-w-0"><p className="truncate text-xs text-slate-300">{String(issue.rule_code)}</p><p className="text-[9px] text-slate-600">{String(issue.severity)}</p></div><span className="text-sm font-medium text-slate-200">{String(issue.count)}</span></div>)}{issues.total_open === 0 ? <p className="py-6 text-center text-xs text-slate-500">暂无未解决质量问题</p> : null}</div></section>
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-slate-200">Shopify Webhook</h2><HealthStatusBadge value={webhooks.lag_seconds != null && Number(webhooks.lag_seconds) <= 120 ? "HEALTHY" : "UNKNOWN"} compact /></div><dl className="mt-4 grid grid-cols-[90px_minmax(0,1fr)] gap-y-2 text-xs"><dt className="text-slate-600">最新事件</dt><dd className="text-slate-300">{dateTime(webhooks.latest_webhook_at)}</dd><dt className="text-slate-600">处理延迟</dt><dd className="text-slate-300">{lagText(webhooks.lag_seconds)}</dd><dt className="text-slate-600">处理状态</dt><dd className="text-slate-300">{webhooks.latest_webhook_at ? String(webhooks.processed) : "无事件"}</dd></dl></section>
        </div>
      </div>
    </div>
  );
}
