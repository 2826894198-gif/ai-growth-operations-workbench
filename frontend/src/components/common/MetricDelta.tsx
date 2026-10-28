export function MetricDelta({ value }: { value?: number | null }) {
  if (value == null) return <span className="text-xs text-slate-500">—</span>;
  const positive = value >= 0;
  return (
    <span className={`text-xs tabular-nums ${positive ? "text-emerald-400" : "text-rose-400"}`}>
      {positive ? "▲" : "▼"} {Math.abs(value).toFixed(1)}%
    </span>
  );
}
