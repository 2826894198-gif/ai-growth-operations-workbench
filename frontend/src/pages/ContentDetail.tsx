import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ErrorState } from "../components/common/ErrorState";
import { Spinner } from "../components/Spinner";
import { TimeSeriesChart } from "../components/charts/v2/TimeSeriesChart";
import { useScope } from "../domain/scope";

function numberText(value: unknown, digits = 0) {
  if (value == null) return "—";
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString("en-US", { maximumFractionDigits: digits }) : "—";
}

function moneyText(value: unknown) {
  if (value == null) return "—";
  const number = Number(value);
  return Number.isFinite(number) ? `$${number.toLocaleString("en-US", { maximumFractionDigits: 2 })}` : "—";
}

function percentText(value: unknown) {
  if (value == null) return "—";
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : "—";
}

function durationText(value: unknown) {
  if (value == null) return "—";
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)} 秒`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} 分 ${Math.round(seconds % 60)} 秒`;
}

function formatDate(value: unknown) {
  if (!value) return "未记录";
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return <div className="min-w-0 rounded-xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-[10px] text-slate-500">{label}</p><p className="mt-2 truncate text-xl font-semibold text-slate-100">{value}</p>{hint ? <p className="mt-1 text-[9px] leading-relaxed text-slate-600">{hint}</p> : null}</div>;
}

export function ContentDetail() {
  const { assetId, publicationId } = useParams();
  const { setScope } = useScope();
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      if (publicationId) setDetail(await api.publication(publicationId, days));
      else if (assetId) setDetail(await api.contentAsset(assetId));
    } catch {
      setError("内容不存在，或数据暂时无法读取。");
    } finally {
      setLoading(false);
    }
  }, [assetId, days, publicationId]);

  useEffect(() => { void load(); }, [load]);

  const isPublication = Boolean(publicationId);
  const organic = ((isPublication ? detail?.organic : detail?.organic_total) ?? {}) as Record<string, unknown>;
  const paid = ((isPublication ? detail?.paid : detail?.paid_total) ?? {}) as Record<string, unknown>;
  const business = (detail?.business ?? {}) as Record<string, unknown>;
  const timeline = (detail?.timeline ?? []) as Array<Record<string, unknown>>;
  const promotions = (detail?.promotions ?? []) as Array<Record<string, unknown>>;
  const publications = (detail?.publications ?? []) as Array<Record<string, unknown>>;
  const header = ((isPublication ? detail?.publication : detail?.asset) ?? {}) as Record<string, unknown>;
  const interactions = ["likes", "comments", "shares", "saves"].reduce((sum, key) => sum + Number(organic[key] || 0), 0);
  const engagementRate = Number(organic.views || 0) ? interactions / Number(organic.views) : null;
  const interactionTimeline = useMemo(() => timeline.map((row) => ({
    ...row,
    interactions: ["likes", "comments", "shares", "saves"].reduce((sum, key) => sum + Number(row[key] || 0), 0),
    follows: Number(row.follows || 0),
  })), [timeline]);

  if (loading && !detail) return <Spinner />;
  if (error && !detail) return <ErrorState message={error} />;
  if (!detail) return <p className="text-sm text-slate-500">内容不存在</p>;

  const createFocus = async () => {
    if (!header.id) return;
    await api.createFocusMonitor({
      workspace_id: "ws_main",
      scope_type: isPublication ? "PUBLICATION" : "CONTENT_ASSET",
      scope_id: String(header.id),
      name: `重点监控 ${String(header.title || header.caption || header.id).slice(0, 40)}`,
      priority: "HIGH",
      refresh_interval_minutes: 15,
      actor: "operator",
    });
    setScope({ [isPublication ? "publicationId" : "contentAssetId"]: String(header.id) });
    await load();
  };

  return (
    <div className="space-y-5 sm:space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {header.account_id ? <Link to={`/accounts/${String(header.account_id)}`} className="text-xs text-slate-500 hover:text-slate-300">← 返回账号视频数据</Link> : <Link to="/content" className="text-xs text-slate-500 hover:text-slate-300">← 返回内容表现</Link>}
          <div className="mt-3 flex flex-wrap items-center gap-2"><span className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] text-slate-400">{String(header.platform ?? "CONTENT")}</span><span className="rounded-md border border-slate-800 px-2 py-1 text-[10px] text-slate-500">{String(header.content_type ?? "UNKNOWN")}</span><span className="text-[10px] text-slate-600">{formatDate(header.published_at)}</span></div>
          <h1 className="mt-3 max-w-4xl text-xl font-semibold leading-snug text-slate-100 sm:text-2xl">{String(header.title || header.caption || "无标题内容")}</h1>
          <p className="mt-2 text-xs text-slate-500">单条内容的自然表现、观众行为和付费放大分开查看</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {isPublication ? <select value={days} onChange={(event) => setDays(Number(event.target.value))} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-300"><option value={7}>近 7 天</option><option value={30}>近 30 天</option><option value={90}>近 90 天</option></select> : null}
          {header.public_url ? <a href={String(header.public_url)} target="_blank" rel="noreferrer" className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300">查看原视频 ↗</a> : null}
          <button onClick={() => void createFocus()} className="rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-xs text-amber-300">☆ 重点监控</button>
        </div>
      </div>

      <section>
        <div className="mb-3 flex items-end justify-between gap-3"><div><h2 className="text-sm font-semibold text-slate-200">核心结果</h2><p className="mt-1 text-[10px] text-slate-600">自然流量表现，不与广告投放合并</p></div>{loading ? <span className="text-[10px] text-sky-400">更新中…</span> : null}</div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <MetricCard label="播放量" value={numberText(organic.views)} hint="平台报告播放事件" />
          <MetricCard label="触达人数" value={numberText(organic.reach)} hint="平台支持时返回" />
          <MetricCard label="总互动" value={numberText(interactions)} hint="赞 + 评 + 分享 + 收藏" />
          <MetricCard label="互动率" value={percentText(engagementRate)} hint="总互动 ÷ 播放量" />
          <MetricCard label="新增关注" value={numberText(organic.follows)} hint="由内容带来的平台关注" />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
        <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
          <div className="mb-4"><h2 className="text-sm font-semibold text-slate-200">播放与触达趋势</h2><p className="mt-1 text-[10px] text-slate-600">观察内容在所选窗口内的流量变化</p></div>
          <TimeSeriesChart dimensions={["date", "views", "reach"]} rows={timeline.map((row) => ({ ...row, views: Number(row.views || 0), reach: Number(row.reach || 0) }))} metrics={[{ key: "views", name: "播放", color: "#38bdf8", area: true }, { key: "reach", name: "触达", color: "#a78bfa" }]} />
        </section>
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
          <h2 className="text-sm font-semibold text-slate-200">互动构成</h2><p className="mt-1 text-[10px] text-slate-600">区分浅层反馈与主动传播</p>
          <div className="mt-5 grid grid-cols-2 gap-3">
            {[["点赞", organic.likes], ["评论", organic.comments], ["分享", organic.shares], ["收藏", organic.saves], ["主页访问", organic.profile_visits], ["新增关注", organic.follows]].map(([label, value]) => <div key={String(label)} className="rounded-xl bg-slate-950/35 p-3"><p className="text-[9px] text-slate-600">{String(label)}</p><p className="mt-1 text-lg font-medium text-slate-200">{numberText(value)}</p></div>)}
          </div>
        </section>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(320px,0.65fr)_minmax(0,1.35fr)]">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
          <h2 className="text-sm font-semibold text-slate-200">观看质量</h2><p className="mt-1 text-[10px] text-slate-600">判断视频是否留得住人</p>
          <dl className="mt-5 space-y-4 text-xs"><div className="flex items-center justify-between gap-4"><dt className="text-slate-500">总观看时长</dt><dd className="font-medium text-slate-200">{durationText(organic.watch_time)}</dd></div><div className="flex items-center justify-between gap-4"><dt className="text-slate-500">平均观看时长</dt><dd className="font-medium text-slate-200">{durationText(organic.average_watch_time)}</dd></div><div className="flex items-center justify-between gap-4"><dt className="text-slate-500">完播率</dt><dd className="font-medium text-emerald-400">{percentText(organic.completion_rate)}</dd></div><div className="flex items-center justify-between gap-4"><dt className="text-slate-500">跳出率</dt><dd className="font-medium text-amber-400">{percentText(organic.skip_rate)}</dd></div></dl>
        </section>
        <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
          <div className="mb-4"><h2 className="text-sm font-semibold text-slate-200">互动与转粉趋势</h2><p className="mt-1 text-[10px] text-slate-600">判断流量是否进一步沉淀为互动和关注</p></div>
          <TimeSeriesChart dimensions={["date", "interactions", "follows"]} rows={interactionTimeline} metrics={[{ key: "interactions", name: "互动", color: "#34d399", area: true }, { key: "follows", name: "新增关注", color: "#fbbf24" }]} />
        </section>
      </div>

      {!isPublication ? <section className="rounded-2xl border border-slate-800 bg-slate-900/60"><div className="border-b border-slate-800 px-5 py-4"><h2 className="text-sm font-semibold text-slate-200">各平台发布</h2><p className="mt-1 text-[10px] text-slate-600">同一素材在不同平台独立统计，再汇总到素材层</p></div><div className="divide-y divide-slate-800">{publications.map((item) => { const publication = item.publication as Record<string, unknown>; const itemOrganic = item.organic as Record<string, unknown>; const itemPaid = item.paid as Record<string, unknown>; return <Link to={`/content/publications/${String(publication.id)}`} key={String(publication.id)} className="flex flex-col gap-2 px-5 py-4 hover:bg-slate-800/20 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm text-slate-200">{String(publication.platform)} · {String(publication.external_post_id)}</p><p className="mt-1 text-[10px] text-slate-600">{formatDate(publication.published_at)}</p></div><p className="text-xs text-slate-500">播放 {numberText(itemOrganic.views)} · 花费 {moneyText(itemPaid.spend)} · ROAS {itemPaid.roas == null ? "—" : `${numberText(itemPaid.roas, 2)}×`}</p></Link>; })}</div></section> : null}

      <section className="rounded-2xl border border-slate-800 bg-slate-900/60">
        <div className="border-b border-slate-800 px-5 py-4"><h2 className="text-sm font-semibold text-slate-200">付费放大</h2><p className="mt-1 text-[10px] text-slate-600">只展示与该内容建立 Promotion Link 后的广告表现</p></div>
        <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4 sm:p-5"><MetricCard label="广告花费" value={moneyText(paid.spend)} /><MetricCard label="广告收入" value={moneyText(paid.revenue)} /><MetricCard label="平台 ROAS" value={paid.roas == null ? "—" : `${numberText(paid.roas, 2)}×`} /><MetricCard label="平台购买" value={numberText(paid.purchases, 2)} /></div>
        <div className="border-t border-slate-800">
          {promotions.map((link) => <div key={String(link.id)} className="flex flex-col gap-2 border-b border-slate-800 px-5 py-4 last:border-b-0 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-xs text-slate-300">{String(link.paid_platform)} · 广告 {String(link.ad_id || "—")} · 活动 {String(link.campaign_id || "—")}</p><p className="mt-1 text-[10px] text-slate-600">映射来源 {String(link.mapping_source)} · 置信度 {numberText(link.mapping_confidence, 2)} · {String(link.status)}</p></div><span className="text-[10px] text-slate-500">开始 {formatDate(link.started_at)}</span></div>)}
          {promotions.length === 0 ? <p className="px-5 py-8 text-center text-sm text-slate-500">暂无投放映射，此处不会把账号广告数据误算到该视频。</p> : null}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-3 rounded-2xl border border-slate-800 bg-slate-950/30 p-4 text-[10px] leading-relaxed text-slate-500 sm:grid-cols-3 sm:p-5"><div><p className="font-medium text-slate-400">自然数据</p><p className="mt-1">播放、触达和互动来自平台报告；跨平台不去重。</p></div><div><p className="font-medium text-slate-400">付费数据</p><p className="mt-1">Promotion Link 之后的广告表现，不代表因果增量。</p></div><div><p className="font-medium text-slate-400">经营数据</p><p className="mt-1">{String(business.caveat || "订单与净收入需建立第一方归因后展示。")}</p></div></section>
    </div>
  );
}
