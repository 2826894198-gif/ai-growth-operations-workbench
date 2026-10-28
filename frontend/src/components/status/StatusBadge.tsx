const tones: Record<string, string> = {
  HEALTHY: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  GOOD: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  WATCH: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  AT_RISK: "bg-orange-500/10 text-orange-400 border-orange-500/30",
  CRITICAL: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  BAD: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  UNKNOWN: "bg-slate-500/10 text-slate-400 border-slate-500/30",
  FRESH: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  DELAYED: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  STALE: "bg-orange-500/10 text-orange-400 border-orange-500/30",
  FAILED: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  COMPLETED: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  RUNNING: "bg-sky-500/10 text-sky-400 border-sky-500/30",
  OPEN: "bg-violet-500/10 text-violet-400 border-violet-500/30",
  ACKNOWLEDGED: "bg-sky-500/10 text-sky-400 border-sky-500/30",
  APPROVED: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  REJECTED: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  LEARNING: "bg-sky-500/10 text-sky-400 border-sky-500/30",
  INSUFFICIENT_DATA: "bg-slate-500/10 text-slate-400 border-slate-500/30",
  DATA_ISSUE: "bg-orange-500/10 text-orange-400 border-orange-500/30",
};

export function StatusBadge({ value }: { value: string }) {
  const tone = tones[value.toUpperCase()] ?? tones.UNKNOWN;
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${tone}`}>
      {value}
    </span>
  );
}
