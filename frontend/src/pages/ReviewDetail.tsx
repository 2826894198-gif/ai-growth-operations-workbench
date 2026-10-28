import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ErrorState } from "../components/common/ErrorState";
import { HealthStatusBadge } from "../components/health/HealthStatusBadge";
import { ReviewMetricCard } from "../components/review/ReviewMetricCard";
import { Spinner } from "../components/Spinner";
import { useScope } from "../domain/scope";

const METRIC_ORDER = ["net_revenue", "paid_spend", "orders", "aov", "blended_roas", "paid_roas", "paid_cpa", "paid_purchases", "content_count", "social_views"];

export function ReviewDetail() {
  const { reviewId } = useParams();
  const { scope } = useScope();
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [followupTitle, setFollowupTitle] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!reviewId) return;
    setLoading(true);
    setError("");
    try { setReview(await api.review(reviewId, scope.workspaceId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "复盘加载失败"); }
    finally { setLoading(false); }
  }, [reviewId, scope.workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const addFollowup = async () => {
    if (!reviewId || !followupTitle.trim()) return;
    await api.createReviewFollowup(reviewId, { workspace_id: scope.workspaceId, title: followupTitle.trim(), owner_id: "operator" });
    setFollowupTitle("");
    await load();
  };

  const finishFollowup = async (id: string) => {
    await api.updateReviewFollowup(id, { workspace_id: scope.workspaceId, status: "DONE", result: "已完成" });
    await load();
  };

  if (loading && !review) return <Spinner />;
  if (error && !review) return <ErrorState message={error} />;
  if (!review) return null;

  const period = (review.period ?? {}) as Record<string, unknown>;
  const metrics = (review.metrics ?? {}) as Record<string, Record<string, unknown>>;
  const followups = (review.followups ?? []) as Array<Record<string, unknown>>;
  const caveats = (review.caveats ?? []) as unknown[];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><Link to="/reviews" className="text-xs text-slate-500 hover:text-slate-300">← 返回数据复盘</Link><span className="text-[10px] text-slate-600">快照 ID {String(review.id)}</span></div>
      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><div className="flex flex-wrap items-center gap-2"><p className="text-xs font-medium uppercase tracking-wider text-sky-400">{String(review.review_type)} REVIEW</p><HealthStatusBadge value={review.data_status} /></div><h1 className="mt-2 text-2xl font-semibold text-slate-100">{String(period.period_start)} 至 {String(period.period_end)}</h1><p className="mt-1 text-xs text-slate-500">对比 {String(period.baseline_start)} 至 {String(period.baseline_end)} · 由 {String(review.created_by)} 保存</p></div><HealthStatusBadge value={review.status} /></div>
        <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/30 p-4"><p className="text-sm leading-relaxed text-slate-300">{String(review.summary ?? "未填写结论")}</p></div>
      </section>

      <section><div className="mb-3"><h2 className="text-sm font-semibold text-slate-200">保存时的指标快照</h2><p className="mt-0.5 text-xs text-slate-500">后续数据回补不会静默改写本次记录。</p></div><div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">{METRIC_ORDER.map((key) => metrics[key] ? <ReviewMetricCard key={key} metric={metrics[key]} /> : null)}</div></section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60">
          <div className="border-b border-slate-800 px-5 py-4"><h2 className="text-sm font-semibold text-slate-200">跟进项</h2><p className="mt-0.5 text-xs text-slate-500">只记录内部工作，不会触发广告或电商平台变更。</p></div>
          <div className="divide-y divide-slate-800">{followups.map((item) => <div key={String(item.id)} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"><div><p className={`text-sm ${item.status === "DONE" ? "text-slate-600 line-through" : "text-slate-300"}`}>{String(item.title)}</p><p className="mt-0.5 text-[10px] text-slate-600">负责人 {String(item.owner_id ?? "未指派")} · {String(item.status)}</p></div>{item.status !== "DONE" ? <button onClick={() => void finishFollowup(String(item.id))} className="self-start rounded-lg border border-emerald-500/30 px-3 py-1.5 text-xs text-emerald-400">标记完成</button> : <HealthStatusBadge value="COMPLETE" compact />}</div>)}{followups.length === 0 ? <p className="px-5 py-8 text-center text-xs text-slate-500">尚未添加跟进项</p> : null}</div>
          <div className="flex flex-col gap-2 border-t border-slate-800 p-4 sm:flex-row"><input value={followupTitle} onChange={(event) => setFollowupTitle(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void addFollowup()} placeholder="例如：检查 Meta 授权并回补昨日数据" className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-sky-500" /><button disabled={!followupTitle.trim()} onClick={() => void addFollowup()} className="rounded-lg bg-sky-500 px-4 py-2 text-xs font-medium text-white disabled:opacity-40">添加跟进</button></div>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"><h2 className="text-sm font-semibold text-slate-200">数据限制</h2><ul className="mt-4 space-y-2 text-xs leading-relaxed text-slate-500">{caveats.map((caveat) => <li key={String(caveat)} className="rounded-lg border border-slate-800 bg-slate-950/30 p-3">{String(caveat)}</li>)}</ul></section>
      </div>
    </div>
  );
}
