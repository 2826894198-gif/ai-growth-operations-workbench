import type { Kpi } from "../../domain/types";
import { StatusBadge } from "../status/StatusBadge";

function formatValue(value: number | null, format: Kpi["format"]) {
  if (value == null) return "—";
  if (format === "currency") return `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (format === "percent") return `${(value * 100).toFixed(1)}%`;
  if (format === "ratio") return `${value.toFixed(2)}×`;
  return Math.round(value).toLocaleString();
}

export function KpiCard({ kpi }: { kpi: Kpi }) {
  const positive = kpi.positive_direction === "up";
  const compare = kpi.compare_pct;
  const goodChange = compare != null && (positive ? compare > 0 : compare < 0);
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wider text-slate-500">{kpi.label}</p>
        <StatusBadge value={kpi.status} />
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">{formatValue(kpi.value, kpi.format)}</p>
      <div className="mt-1 flex items-center gap-2 text-xs">
        {compare != null ? (
          <span className={goodChange ? "text-emerald-400" : "text-rose-400"}>
            {compare > 0 ? "▲" : "▼"} {Math.abs(compare).toFixed(1)}%
          </span>
        ) : (
          <span className="text-slate-500">无对比</span>
        )}
        {kpi.target != null ? <span className="text-slate-500">目标 {formatValue(kpi.target, kpi.format)}</span> : null}
      </div>
    </div>
  );
}
