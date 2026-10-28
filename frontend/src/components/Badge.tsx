interface BadgeProps {
  value: string;
}

const tones: Record<string, string> = {
  HEALTHY: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  DEGRADED: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  UNHEALTHY: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  UNKNOWN: "bg-slate-500/10 text-slate-400 border-slate-500/30",
  RUNNING: "bg-sky-500/10 text-sky-400 border-sky-500/30",
  INACTIVE: "bg-slate-500/10 text-slate-400 border-slate-500/30",
  QUEUED: "bg-violet-500/10 text-violet-400 border-violet-500/30",
  SUCCESS: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  FAILED: "bg-rose-500/10 text-rose-400 border-rose-500/30",
  CANCELLED: "bg-slate-500/10 text-slate-400 border-slate-500/30",
  TIMEOUT: "bg-orange-500/10 text-orange-400 border-orange-500/30",
};

export function Badge({ value }: BadgeProps) {
  const tone = tones[value.toUpperCase()] ?? tones.UNKNOWN;
  return (
    <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-medium ${tone}`}>
      {value}
    </span>
  );
}
