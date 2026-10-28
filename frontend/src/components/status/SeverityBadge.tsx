const tones: Record<string, string> = {
  INFO: "bg-slate-500/10 text-slate-400 border-slate-500/30",
  LOW: "bg-sky-500/10 text-sky-400 border-sky-500/30",
  MEDIUM: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  HIGH: "bg-orange-500/10 text-orange-400 border-orange-500/30",
  CRITICAL: "bg-rose-500/10 text-rose-400 border-rose-500/30",
};

export function SeverityBadge({ value }: { value: string }) {
  const tone = tones[value.toUpperCase()] ?? tones.INFO;
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${tone}`}>
      {value}
    </span>
  );
}
