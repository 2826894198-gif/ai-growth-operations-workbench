import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { TimeSeriesChart } from "../components/charts/v2/TimeSeriesChart";
import { ErrorState } from "../components/common/ErrorState";
import { HealthStatusBadge } from "../components/health/HealthStatusBadge";
import { ReviewMetricCard } from "../components/review/ReviewMetricCard";
import { Spinner } from "../components/Spinner";
import { useScope } from "../domain/scope";

const METRIC_ORDER = ["net_revenue", "paid_spend", "orders", "aov", "blended_roas", "paid_roas", "paid_cpa", "paid_purchases", "content_count", "social_views"];

function periodText(period: Record<string, unknown>) {
  return `${String(period.period_start ?? "—")} 至 ${String(period.period_end ?? "—")}`;
}

export function Reviews() {
  const navigate = useNavigate();
  const { scope } = useScope();
  const [reviewType, setReviewType] = useState("DAILY");
  const [customDays, setCustomDays] = useState(14);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [reviews, setReviews] = useState<Array<Record<string, unknown>>>([]);
  const [trendRows, setTrendRows] = useState<Array<Record<string, unknown>>>([]);
  const [campaignRows, setCampaignRows] = useState<Array<Record<string, unknown>>>([]);
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const trendDays = reviewType === "DAILY" ? 7 : reviewType === "WEEKLY" ? 14 : Math.min(customDays, 30);
      const [previewData, reviewRows, trendData, campaignData] = await Promise.all([
        api.reviewPreview(scope.workspaceId, reviewType, scope.accountIds, reviewType === "CUSTOM" ? customDays : undefined),
        api.reviews(scope.workspaceId),
        api.reviewTrends(scope.workspaceId, trendDays, scope.accountIds),
        api.reviewCampaigns(scope.workspaceId, reviewType, scope.accountIds, reviewType === "CUSTOM" ? customDays : undefined),
      ]);
      setPreview(previewData);
      setReviews(reviewRows);
      setSummary(String(previewData.summary ?? ""));
      setTrendRows((trendData.rows ?? []) as Array<Record<string, unknown>>);
      setCampaignRows((campaignData.rows ?? []) as Array<Record<string, unknown>>);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "复盘数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [customDays, reviewType, scope.accountIds, scope.workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const record = await api.createReview({
        workspace_id: scope.workspaceId,
        review_type: reviewType,
        days: reviewType === "CUSTOM" ? customDays : undefined,
        account_ids: scope.accountIds,
        summary,
        created_by: "operator",
      });
      navigate(`/reviews/${String(record.id)}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存复盘失败");
    } finally {
      setSaving(false);
    }
  };

  const period = (preview?.period ?? {}) as Record<string, unknown>;
  const metrics = (preview?.metrics ?? {}) as Record<string, Record<string, unknown>>;
  const findings = (preview?.findings ?? []) as Array<Record<string, unknown>>;
  const caveats = (preview?.caveats ?? []) as unknown[];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-sky-400">Evidence-backed review</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">数据复盘</h1>
          <p className="mt-1 text-sm text-slate-500">先确认数据可用性，再保存有证据的经营结论。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-slate-700 bg-slate-900 p-1">
            {[['DAILY', '日复盘'], ['WEEKLY', '周复盘'], ['CUSTOM', '自定义']].map(([value, label]) => <button key={value} onClick={() => setReviewType(value)} className={`rounded-md px-3 py-1.5 text-xs ${reviewType === value ? "bg-sky-500 text-white" : "text-slate-400 hover:text-slate-200"}`}>{label}</button>)}
          </div>
          {reviewType === "CUSTOM" ? <select value={customDays} onChange={(event) => setCustomDays(Number(event.target.value))} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-300"><option value={7}>7 天</option><option value={14}>14 天</option><option value={30}>30 天</option><option value={60}>60 天</option></select> : null}
        </div>
      </div>

      {error ? <ErrorState message={error} /> : null}
      {loading && !preview ? <Spinner /> : null}

      {preview ? (
        <>
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-semibold text-slate-100">{reviewType === "DAILY" ? "日复盘预览" : reviewType === "WEEKLY" ? "周复盘预览" : "自定义复盘预览"}</h2><HealthStatusBadge value={preview.data_status} /></div>
                <p className="mt-1 text-xs text-slate-500">当前周期 {periodText(period)} · 对比 {String(period.baseline_start)} 至 {String(period.baseline_end)}</p>
              </div>
              <button onClick={() => void load()} className="self-start rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300">重新计算</button>
            </div>
            {preview.data_status !== "COMPLETE" ? <div className="mt-4 rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-xs leading-relaxed text-amber-300">当前数据为 {String(preview.data_status)}，页面允许查看和保存，但结论会保留数据限制，不应直接解读为业务变化。</div> : null}
          </section>

          <section>
            <div className="mb-3"><h2 className="text-sm font-semibold text-slate-200">核心指标</h2><p className="mt-0.5 text-xs text-slate-500">当前周期与上一等长周期对比；比例指标按总分子/总分母重算。</p></div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">{METRIC_ORDER.map((key) => metrics[key] ? <ReviewMetricCard key={key} metric={metrics[key]} /> : null)}</div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
            <div><h2 className="text-sm font-semibold text-slate-200">经营趋势</h2><p className="mt-0.5 text-xs text-slate-500">用于判断变化是单日波动还是连续趋势；空值不会自动按零处理。</p></div>
            <div className="mt-4"><TimeSeriesChart dimensions={["date", "net_revenue", "paid_spend"]} rows={trendRows} metrics={[{ key: "net_revenue", name: "净收入", color: "#34d399", area: true }, { key: "paid_spend", name: "广告花费", color: "#38bdf8" }]} dataZoom={trendRows.length > 14} height="h-72" /></div>
          </section>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
            <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <div className="flex items-center justify-between"><div><h2 className="text-sm font-semibold text-slate-200">复盘结论</h2><p className="mt-0.5 text-xs text-slate-500">可以编辑表述，保存后指标快照不会静默改变。</p></div><span className="text-[10px] text-slate-600">内部留痕 · 不写外部平台</span></div>
              <textarea value={summary} onChange={(event) => setSummary(event.target.value)} rows={5} className="mt-4 w-full resize-y rounded-xl border border-slate-700 bg-slate-950/50 p-4 text-sm leading-relaxed text-slate-200 outline-none focus:border-sky-500" />
              <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><p className="text-[10px] text-slate-600">请使用“相关”“同时发生”“可能驱动”，避免把相关性写成确定因果。</p><button disabled={saving || !summary.trim()} onClick={() => void save()} className="min-h-10 rounded-lg bg-sky-500 px-5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40">{saving ? "保存中…" : "保存本次复盘"}</button></div>
            </section>

            <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
              <h2 className="text-sm font-semibold text-slate-200">主要发现</h2>
              <div className="mt-4 space-y-3">{findings.map((finding, index) => <div key={`${String(finding.metric_key)}-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/30 p-3"><div className="flex items-start gap-2"><HealthStatusBadge value={finding.severity} compact /><p className="text-xs font-medium leading-relaxed text-slate-300">{String(finding.title)}</p></div><p className="mt-2 text-[10px] leading-relaxed text-slate-600">{String(finding.description)}</p></div>)}{findings.length === 0 ? <p className="py-6 text-center text-xs text-slate-500">当前没有达到阈值的变化</p> : null}</div>
            </section>
          </div>

          <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
            <div className="flex flex-col gap-2 border-b border-slate-800 px-5 py-4 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-sm font-semibold text-slate-200">Campaign 变化下钻</h2><p className="mt-0.5 text-xs text-slate-500">从花费和平台 ROAS 变化定位可能驱动；平台收入不等于第一方净收入。</p></div><span className="text-[10px] text-slate-600">按当前周期花费排序</span></div>
            <div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[900px] text-left text-xs"><thead className="bg-slate-950/30 text-slate-500"><tr><th className="px-5 py-3">Campaign</th><th>平台</th><th>花费</th><th>花费环比</th><th>平台 ROAS</th><th>ROAS 环比</th><th>购买</th><th>CTR</th></tr></thead><tbody className="divide-y divide-slate-800">{campaignRows.map((campaign) => <tr key={String(campaign.campaign_id)} className="text-slate-400 hover:bg-slate-800/20"><td className="max-w-xs px-5 py-4"><Link to={`/ads/campaigns/${String(campaign.campaign_id)}`} className="font-medium text-slate-200 hover:text-sky-400">{String(campaign.name)}</Link><p className="mt-1 text-[10px] text-slate-600">{String(campaign.status ?? "UNKNOWN")}</p></td><td>{String(campaign.platform)}</td><td className="tabular-nums text-slate-200">${Number(campaign.spend || 0).toFixed(2)}</td><td className={Number(campaign.spend_delta_percent || 0) > 0 ? "text-amber-400" : "text-slate-400"}>{campaign.spend_delta_percent == null ? "—" : `${Number(campaign.spend_delta_percent) > 0 ? "+" : ""}${Number(campaign.spend_delta_percent).toFixed(1)}%`}</td><td>{campaign.roas == null ? "—" : `${Number(campaign.roas).toFixed(2)}×`}</td><td className={Number(campaign.roas_delta_percent || 0) < 0 ? "text-rose-400" : "text-emerald-400"}>{campaign.roas_delta_percent == null ? "—" : `${Number(campaign.roas_delta_percent) > 0 ? "+" : ""}${Number(campaign.roas_delta_percent).toFixed(1)}%`}</td><td>{Number(campaign.purchases || 0).toFixed(0)}</td><td>{campaign.ctr == null ? "—" : `${Number(campaign.ctr).toFixed(2)}%`}</td></tr>)}</tbody></table></div>
            <div className="divide-y divide-slate-800 md:hidden">{campaignRows.map((campaign) => <Link key={String(campaign.campaign_id)} to={`/ads/campaigns/${String(campaign.campaign_id)}`} className="block p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-medium text-slate-200">{String(campaign.name)}</p><p className="mt-1 text-[10px] text-slate-600">{String(campaign.platform)} · {String(campaign.status ?? "UNKNOWN")}</p></div><p className="shrink-0 text-sm font-medium text-slate-200">${Number(campaign.spend || 0).toFixed(2)}</p></div><div className="mt-3 grid grid-cols-3 gap-2 text-[10px] text-slate-500"><span>花费环比<br />{campaign.spend_delta_percent == null ? "—" : `${Number(campaign.spend_delta_percent).toFixed(1)}%`}</span><span>平台 ROAS<br />{campaign.roas == null ? "—" : `${Number(campaign.roas).toFixed(2)}×`}</span><span>购买<br />{Number(campaign.purchases || 0).toFixed(0)}</span></div></Link>)}</div>
            {!campaignRows.length ? <p className="px-5 py-12 text-center text-sm text-slate-500">当前周期没有 Campaign 数据</p> : null}
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5"><h2 className="text-sm font-semibold text-slate-200">数据限制</h2><ul className="mt-3 grid gap-2 text-xs leading-relaxed text-slate-500 md:grid-cols-2">{caveats.map((caveat) => <li key={String(caveat)} className="rounded-lg border border-slate-800 bg-slate-950/20 px-3 py-2">{String(caveat)}</li>)}</ul></section>
        </>
      ) : null}

      <section className="rounded-2xl border border-slate-800 bg-slate-900/60">
        <div className="border-b border-slate-800 px-5 py-4"><h2 className="text-sm font-semibold text-slate-200">历史复盘</h2><p className="mt-0.5 text-xs text-slate-500">保存后的指标快照、结论和跟进项</p></div>
        <div className="divide-y divide-slate-800">{reviews.map((review) => { const rowPeriod = (review.period ?? {}) as Record<string, unknown>; return <Link key={String(review.id)} to={`/reviews/${String(review.id)}`} className="grid gap-3 px-5 py-4 hover:bg-slate-800/20 sm:grid-cols-[120px_180px_minmax(0,1fr)_auto] sm:items-center"><span className="text-xs font-medium text-slate-300">{String(review.review_type)}</span><span className="text-xs text-slate-500">{periodText(rowPeriod)}</span><span className="line-clamp-1 text-xs text-slate-400">{String(review.summary ?? "未填写总结")}</span><HealthStatusBadge value={review.data_status} compact /></Link>; })}{reviews.length === 0 ? <p className="px-5 py-10 text-center text-sm text-slate-500">尚未保存复盘</p> : null}</div>
      </section>
    </div>
  );
}
