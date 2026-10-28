import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ChartFrame } from "../components/charts/v2/ChartFrame";
import { HorizontalBarChart } from "../components/charts/v2/HorizontalBarChart";
import { DataBoundaryBanner } from "../components/common/DataBoundaryBanner";
import { ErrorState } from "../components/common/ErrorState";
import { HealthStatusBadge } from "../components/health/HealthStatusBadge";
import { Spinner } from "../components/Spinner";
import { useScope } from "../domain/scope";

type DataRecord = Record<string, unknown>;

function number(value: unknown) {
  const parsed = Number(value);
  return value == null || !Number.isFinite(parsed) ? null : parsed;
}

function money(value: unknown) {
  const parsed = number(value);
  return parsed == null ? "—" : `$${parsed.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function count(value: unknown) {
  const parsed = number(value);
  return parsed == null ? "—" : parsed.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function candidateConfidence(value: unknown) {
  const parsed = number(value);
  return parsed == null ? "—" : `${(parsed * 100).toFixed(0)}%`;
}

export function SearchIntelligence() {
  const { scope } = useScope();
  const [terms, setTerms] = useState<DataRecord[]>([]);
  const [negatives, setNegatives] = useState<DataRecord[]>([]);
  const [expansion, setExpansion] = useState<DataRecord[]>([]);
  const [health, setHealth] = useState<DataRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const [termResult, negativeResult, expansionResult, healthResult] = await Promise.allSettled([
      api.searchTerms(),
      api.searchNegatives(),
      api.searchExpansion(),
      api.healthSummary(scope.workspaceId),
    ]);

    if (termResult.status === "fulfilled") setTerms(termResult.value as DataRecord[]);
    if (negativeResult.status === "fulfilled") setNegatives(negativeResult.value as DataRecord[]);
    if (expansionResult.status === "fulfilled") setExpansion(expansionResult.value as DataRecord[]);
    if (healthResult.status === "fulfilled") setHealth(healthResult.value);

    const failed = [termResult, negativeResult, expansionResult].filter((result) => result.status === "rejected");
    if (failed.length) setError(failed.length === 3 ? "搜索数据加载失败，请检查 Google Ads 搜索词源。" : "部分搜索数据暂时无法加载，页面仅展示已成功读取的模块。");
    setLoading(false);
  }, [scope.workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const spendAvailable = terms.some((term) => number(term.spend) != null);
  const conversionAvailable = terms.some((term) => number(term.conversions) != null);
  const chartRows = useMemo(
    () => terms
      .filter((term) => number(term.spend) != null)
      .sort((a, b) => (number(b.spend) ?? 0) - (number(a.spend) ?? 0))
      .slice(0, 8)
      .map((term) => ({ label: String(term.term ?? "未命名搜索词"), value: number(term.spend) ?? 0 })),
    [terms],
  );
  const totalSpend = useMemo(() => terms.reduce((sum, term) => sum + (number(term.spend) ?? 0), 0), [terms]);
  const totalConversions = useMemo(() => terms.reduce((sum, term) => sum + (number(term.conversions) ?? 0), 0), [terms]);

  if (loading && !terms.length && !negatives.length && !expansion.length) return <Spinner />;

  return (
    <div className="space-y-5 pb-8 sm:space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-sky-400">Search intelligence</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">搜索智能</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">从搜索词原始表现出发，拆出否定词和扩词候选；候选只进入人工审批，不会在这里直接写回广告平台。</p>
        </div>
        <button type="button" onClick={() => void load()} className="self-start min-h-10 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:border-sky-500 hover:text-sky-300">重新读取</button>
      </header>

      {error ? <ErrorState message={error} /> : null}
      <DataBoundaryBanner dataMode={health?.data_mode} dataUsable={health ? Boolean(health.data_usable) : undefined} evaluatedAt={health?.evaluated_at} blockingReasons={(health?.blocking_reasons ?? []) as unknown[]} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["可用搜索词", terms.length ? count(terms.length) : "—", "GoogleSearchTermDaily 聚合"],
          ["搜索词花费", spendAvailable ? money(totalSpend) : "—", "当前窗口可加总花费"],
          ["搜索词转化", conversionAvailable ? count(totalConversions) : "—", "不等同于第一方订单"],
          ["候选待审", negatives.length + expansion.length ? count(negatives.length + expansion.length) : "—", "仅业务审批，不自动执行"],
        ].map(([label, value, hint]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5"><p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">{value}</p><p className="mt-1 text-[10px] leading-relaxed text-slate-600">{hint}</p></div>)}
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <ChartFrame title="搜索词花费排行" subtitle="按当前窗口聚合；这里只比较搜索词花费，不推断关键词增量价值。" quality={{ status: loading ? "loading" : chartRows.length ? "ready" : "empty", source: "GoogleSearchTermDaily", caveat: "意图和商业相关性当前由源数据提供，UNKNOWN 不代表低价值。" }}>
          <HorizontalBarChart rows={chartRows} color="#a78bfa" height="h-80" ariaLabel="搜索词花费排行" />
        </ChartFrame>

        <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3"><div><h2 className="text-sm font-semibold text-slate-200">判断边界</h2><p className="mt-1 text-[10px] leading-relaxed text-slate-500">先看原始搜索词，再决定是否进入策略。</p></div><HealthStatusBadge value={health?.data_usable === false ? "WARNING" : "UNKNOWN"} compact /></div>
          <div className="mt-5 space-y-3 text-xs leading-relaxed text-slate-400">
            <div className="rounded-xl border border-slate-800 bg-slate-950/30 p-3"><p className="font-medium text-slate-200">原始层</p><p className="mt-1 text-slate-500">花费、点击、转化和 CPA 来自搜索词日表，缺失字段保留为 “—”。</p></div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/30 p-3"><p className="font-medium text-slate-200">复核层</p><p className="mt-1 text-slate-500">否定词/扩词候选是规则筛选结果，必须经过业务审批和策略范围校验。</p></div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/30 p-3"><p className="font-medium text-slate-200">执行层</p><p className="mt-1 text-slate-500">本页不修改 Google Ads；需要执行时进入审批和执行队列。</p></div>
          </div>
          <Link to="/execution/approvals" className="mt-4 inline-flex min-h-10 items-center text-xs text-sky-400">查看审批队列 →</Link>
        </section>
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
        <div className="flex flex-col gap-2 border-b border-slate-800 px-4 py-4 sm:flex-row sm:items-end sm:justify-between sm:px-5"><div><h2 className="text-sm font-semibold text-slate-200">搜索词原始表现</h2><p className="mt-1 text-xs text-slate-500">按花费降序展示；意图字段仍以源数据为准。</p></div><span className="text-[10px] text-slate-600">最多展示 50 条</span></div>
        <div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[760px] text-left text-xs"><thead className="bg-slate-950/30 text-slate-500"><tr><th className="px-5 py-3">搜索词</th><th>意图</th><th>花费</th><th>点击</th><th>转化</th><th>CPA</th><th>商业相关性</th></tr></thead><tbody className="divide-y divide-slate-800">{terms.slice(0, 50).map((term, index) => <tr key={`${String(term.term ?? "term")}-${index}`} className="text-slate-400 hover:bg-slate-800/20"><td className="max-w-[260px] truncate px-5 py-3 font-medium text-slate-200">{String(term.term ?? "未命名搜索词")}</td><td><span className="rounded-full border border-slate-700 px-2 py-1 text-[10px]">{String(term.intent ?? "UNKNOWN")}</span></td><td className="tabular-nums text-slate-200">{money(term.spend)}</td><td className="tabular-nums">{count(term.clicks)}</td><td className="tabular-nums">{count(term.conversions)}</td><td className="tabular-nums">{money(term.cpa)}</td><td>{String(term.commercial_relevance ?? "UNKNOWN")}</td></tr>)}</tbody></table></div>
        <div className="divide-y divide-slate-800 md:hidden">{terms.slice(0, 50).map((term, index) => <div key={`${String(term.term ?? "term")}-${index}`} className="p-4"><div className="flex items-start justify-between gap-3"><p className="min-w-0 truncate text-sm font-medium text-slate-200">{String(term.term ?? "未命名搜索词")}</p><span className="shrink-0 rounded-full border border-slate-700 px-2 py-1 text-[10px] text-slate-400">{String(term.intent ?? "UNKNOWN")}</span></div><div className="mt-3 grid grid-cols-3 gap-3 text-[10px] text-slate-500"><span>花费<br /><b className="font-medium text-slate-300">{money(term.spend)}</b></span><span>点击<br /><b className="font-medium text-slate-300">{count(term.clicks)}</b></span><span>转化<br /><b className="font-medium text-slate-300">{count(term.conversions)}</b></span></div><p className="mt-2 text-[10px] text-slate-600">CPA {money(term.cpa)} · 商业相关性 {String(term.commercial_relevance ?? "UNKNOWN")}</p></div>)}{!terms.length ? <p className="px-5 py-12 text-center text-sm text-slate-500">当前窗口没有搜索词数据</p> : null}</div>
        {terms.length === 0 ? <p className="hidden px-5 py-12 text-center text-sm text-slate-500 md:block">当前窗口没有搜索词数据</p> : null}
      </section>

      <div className="grid min-w-0 gap-4 xl:grid-cols-2">
        <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5"><div className="flex items-start justify-between gap-3"><div><h2 className="text-sm font-semibold text-slate-200">否定词候选</h2><p className="mt-1 text-xs leading-relaxed text-slate-500">高花费且无转化的规则候选；不是自动否定建议。</p></div><HealthStatusBadge value={negatives.length ? "WARNING" : "UNKNOWN"} compact /></div><div className="mt-4 space-y-2">{negatives.slice(0, 20).map((candidate, index) => <div key={`${String(candidate.term ?? "candidate")}-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/40 p-3"><div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div className="min-w-0"><p className="truncate text-sm font-medium text-slate-200">{String(candidate.term ?? "未命名搜索词")}</p><p className="mt-1 text-[10px] text-slate-500">花费 {money(candidate.spend)} · 点击 {count(candidate.clicks)} · 转化 {count(candidate.conversions)}</p></div><span className="shrink-0 text-[10px] text-amber-400">置信度 {candidateConfidence(candidate.negative_candidate_confidence)}</span></div><p className="mt-2 text-[10px] text-slate-600">建议匹配：{String(candidate.recommended_match_type ?? "人工审核")} · 语义分类：{String(candidate.semantic_class ?? "UNKNOWN")}</p></div>)}{!negatives.length ? <p className="rounded-xl border border-dashed border-slate-700 px-4 py-10 text-center text-xs text-slate-500">暂无否定词候选</p> : null}</div></section>

        <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5"><div className="flex items-start justify-between gap-3"><div><h2 className="text-sm font-semibold text-slate-200">扩词候选</h2><p className="mt-1 text-xs leading-relaxed text-slate-500">达到转化阈值的搜索词；需结合意图和落地页质量复核。</p></div><HealthStatusBadge value={expansion.length ? "INFO" : "UNKNOWN"} compact /></div><div className="mt-4 space-y-2">{expansion.slice(0, 20).map((candidate, index) => <div key={`${String(candidate.term ?? "candidate")}-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/40 p-3"><div className="flex items-start justify-between gap-3"><p className="min-w-0 truncate text-sm font-medium text-slate-200">{String(candidate.term ?? "未命名搜索词")}</p><span className="shrink-0 text-[10px] text-emerald-400">转化 {count(candidate.conversions)}</span></div><p className="mt-2 text-[10px] text-slate-500">CPA {money(candidate.cpa)} · 转化价值 {money(candidate.conversion_value)}</p><p className="mt-2 text-[10px] text-slate-600">下一步：业务确认匹配类型、预算边界和首个观测窗口。</p></div>)}{!expansion.length ? <p className="rounded-xl border border-dashed border-slate-700 px-4 py-10 text-center text-xs text-slate-500">暂无扩词候选</p> : null}</div></section>
      </div>
    </div>
  );
}
