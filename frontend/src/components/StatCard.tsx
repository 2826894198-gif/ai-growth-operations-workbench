interface StatCardProps {
  label: string;
  value: number;
  tone?: "default" | "good" | "warn" | "bad";
  hint?: string;
}

const tones: Record<string, string> = {
  default: "text-slate-100",
  good: "text-emerald-400",
  warn: "text-amber-400",
  bad: "text-rose-400",
};

export function StatCard({ label, value, tone = "default", hint }: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-3xl font-semibold ${tones[tone]}`}>{value}</p>
      {hint ? <p className="mt-1 text-[10px] leading-tight text-slate-600">{hint}</p> : null}
    </div>
  );
}
