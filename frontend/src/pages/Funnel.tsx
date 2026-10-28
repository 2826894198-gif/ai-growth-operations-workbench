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

const STAGE_LABELS: Record<string, string> = {
  CLICK: "链接点击",
  LANDING_PAGE: "落地页访问",
  ADD_TO_CART: "加入购物车",
  CHECKOUT: "发起结账",
  PURCHASE: "购买",
};

function number(value: unknown) {
  const parsed = Number(value);
  return value == null || !Number.isFinite(parsed) ? null : parsed;
}

function formatCount(value: unknown) {
  const parsed = number(value);
  return parsed == null ? "—" : parsed.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function formatPercent(value: unknown) {
  const parsed = number(value);
  return parsed == null ? "—" : `${(parsed * 100).toFixed(1)}%`;
}

export function Funnel() {
  const { scope } = useScope();
  const [data, setData] = useState<DataRecord | null>(null);
  const [health, setHealth] = useState<DataRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const [funnelResult, healthResult] = await Promise.allSettled([
      api.funnelOverview(),
      api.healthSummary(scope.workspaceId),
    ]);
    if (funnelResult.status === "fulfilled") setData(funnelResult.value);
    if (healthResult.status === "fulfilled") setHealth(healthResult.value);
    if (funnelResult.status === "rejected") setError(funnelResult.reason instanceof Error ? funnelResult.reason.message : "转化漏斗加载失败");
    setLoading(false);
  }, [scope.workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const stages = (data?.stages ?? []) as DataRecord[];
  const diagnosis = (data?.diagnosis ?? {}) as DataRecord;
  const availableStages = useMemo(() => stages.filter((stage) => Boolean(stage.available) && number(stage.volume) != null), [stages]);
  const chartRows = useMemo(() => availableStages.map((stage) => ({ label: STAGE_LABELS[String(stage.stage)] ?? String(stage.stage), value: number(stage.volume) ?? 0 })), [availableStages]);
  const firstVolume = number(availableStages[0]?.volume);
  const purchaseStage = stages.find((stage) => String(stage.stage) === "PURCHASE");
  const diagnosisProblem = diagnosis.primary_problem ? String(diagnosis.primary_problem) : "暂无规则命中的主要问题";

  if (loading && !data) return <Spinner />;

  return (
    <div className="space-y-5 pb-8 sm:space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0"><p className="text-xs font-medium uppercase tracking-[0.18em] text-sky-400">Conversion funnel</p><h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">转化漏斗</h1><p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">把点击、落地页、加购、结账和购买拆开查看；缺少源事件时保留不可用边界，不把缺失当成 0。</p></div>
        <button type="button" onClick={() => void load()} className="self-start min-h-10 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:border-sky-500 hover:text-sky-300">重新读取</button>
      </header>

      {error ? <ErrorState message={error} /> : null}
      <DataBoundaryBanner dataMode={health?.data_mode} dataUsable={health ? Boolean(health.data_usable) : undefined} evaluatedAt={health?.evaluated_at} blockingReasons={(health?.blocking_reasons ?? []) as unknown[]} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["可用阶段", availableStages.length ? `${availableStages.length}/${stages.length}` : "—", "MetaActionDaily 可读取事件"],
          ["入口量级", formatCount(firstVolume), "当前窗口首个可用阶段"],
          ["购买量", formatCount(purchaseStage?.available ? purchaseStage.volume : null), "平台事件，不等于第一方订单"],
          ["规则诊断", diagnosis.primary_problem ? "需关注" : "—", String(diagnosis.source ?? "RULE")],
        ].map(([label, value, hint]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5"><p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">{value}</p><p className="mt-1 text-[10px] leading-relaxed text-slate-600">{hint}</p></div>)}
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <ChartFrame title="漏斗阶段量级" subtitle="按照事件发生顺序展示；横向长度只比较同一窗口内的事件量。" quality={{ status: loading ? "loading" : chartRows.length ? "ready" : "empty", source: "MetaActionDaily", caveat: "跨阶段事件可能存在重复用户，不能直接当作唯一人数。" }}>
          <HorizontalBarChart rows={chartRows} color="#38bdf8" height="h-80" ariaLabel="转化漏斗阶段量级" />
        </ChartFrame>

        <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5"><div className="flex items-start justify-between gap-3"><div><h2 className="text-sm font-semibold text-slate-200">规则诊断</h2><p className="mt-1 text-[10px] leading-relaxed text-slate-500">只有达到规则条件时才给出问题提示。</p></div><HealthStatusBadge value={diagnosis.primary_problem ? "WARNING" : "UNKNOWN"} compact /></div><div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/30 p-4"><p className="text-xs font-medium text-slate-200">{diagnosisProblem}</p><p className="mt-2 text-[10px] leading-relaxed text-slate-500">诊断来源：{String(diagnosis.source ?? "RULE")}。这不是 AI 自主结论，仍需结合数据健康和第一方订单复核。</p></div><Link to="/reviews" className="mt-4 inline-flex min-h-10 items-center text-xs text-sky-400">进入数据复盘 →</Link></section>
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60"><div className="border-b border-slate-800 px-4 py-4 sm:px-5"><h2 className="text-sm font-semibold text-slate-200">阶段明细</h2><p className="mt-1 text-xs text-slate-500">每一步展示原始事件量和相对上一步的转化率。</p></div><div className="divide-y divide-slate-800">{stages.map((stage) => <div key={String(stage.stage)} className="grid gap-3 px-4 py-4 sm:grid-cols-[minmax(150px,1.2fr)_140px_160px_auto] sm:items-center sm:px-5"><div><p className="text-sm font-medium text-slate-200">{STAGE_LABELS[String(stage.stage)] ?? String(stage.stage)}</p><p className="mt-1 text-[10px] text-slate-600">原始事件：{String(stage.stage)}</p></div><div><p className="text-[9px] text-slate-600">事件量</p><p className="mt-1 tabular-nums text-slate-200">{stage.available ? formatCount(stage.volume) : "—"}</p></div><div><p className="text-[9px] text-slate-600">步骤转化</p><p className="mt-1 tabular-nums text-slate-300">{stage.available ? formatPercent(stage.step_conversion) : "—"}</p></div><span className={`justify-self-start rounded-full border px-2 py-1 text-[10px] ${stage.available ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" : "border-slate-700 bg-slate-950/30 text-slate-500"}`}>{stage.available ? "可用" : "不可用"}</span></div>)}{!stages.length ? <div className="px-5 py-14 text-center"><p className="text-sm text-slate-300">当前没有漏斗阶段定义</p><p className="mt-1 text-xs text-slate-500">请检查 Meta 事件源配置。</p></div> : null}</div></section>
    </div>
  );
}
