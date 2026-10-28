function displayValue(metric: Record<string, unknown>) {
  const value = metric.value;
  if (value == null) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  if (metric.unit === "currency") return `$${numeric.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  if (metric.unit === "ratio") return `${numeric.toFixed(2)}×`;
  return numeric.toLocaleString("en-US", { maximumFractionDigits: 1 });
}

export function ReviewMetricCard({ metric }: { metric: Record<string, unknown> }) {
  const delta = metric.delta_percent == null ? null : Number(metric.delta_percent);
  const unavailable = metric.status === "NO_DATA";
  return (
    <div className="min-w-0 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="min-w-0">
        <p className="truncate text-xs text-slate-500">{String(metric.label ?? metric.metric_key)}</p>
        <span className="mt-2 inline-flex max-w-full truncate rounded bg-slate-800 px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-slate-500">
          {String(metric.measurement_basis ?? metric.source ?? "未知来源")}
        </span>
      </div>
      <p className={`mt-3 text-2xl font-semibold ${unavailable ? "text-slate-600" : "text-slate-100"}`}>{displayValue(metric)}</p>
      <div className="mt-2 flex min-h-5 items-center gap-2 text-[10px]">
        {delta == null ? <span className="text-slate-600">无可比基线</span> : <span className={delta >= 0 ? "text-emerald-400" : "text-rose-400"}>{delta >= 0 ? "↑" : "↓"} {Math.abs(delta).toFixed(1)}%</span>}
        {metric.freshness ? <span className="truncate text-slate-600">{String(metric.freshness)}</span> : null}
      </div>
    </div>
  );
}
