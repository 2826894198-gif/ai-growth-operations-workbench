interface MetricCardProps {
  label: string;
  value: number | string | null;
  hint?: string;
  tone?: "default" | "good" | "warn" | "bad";
  basis?: string;
  freshness?: string;
}

const tones: Record<string, string> = {
  default: "text-slate-100",
  good: "text-emerald-400",
  warn: "text-amber-400",
  bad: "text-rose-400",
};

export function MetricCard({ label, value, hint, tone = "default", basis, freshness }: MetricCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-3xl font-semibold ${tones[tone]}`}>{value ?? "—"}</p>
      {basis ? <p className="mt-1 text-[10px] text-slate-600">口径：{basis}</p> : null}
      {freshness ? <p className="text-[10px] text-slate-600">新鲜度：{freshness}</p> : null}
      {hint ? <p className="mt-1 text-[10px] leading-tight text-slate-600">{hint}</p> : null}
    </div>
  );
}
