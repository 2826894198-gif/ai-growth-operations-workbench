const labels: Record<string, string> = {
  HEALTHY: "正常",
  WARNING: "需观察",
  AT_RISK: "高风险",
  CRITICAL: "严重",
  UNKNOWN: "未知",
  FRESH: "新鲜",
  DELAYED: "延迟",
  STALE: "过期",
  COMPLETE: "完整",
  PARTIAL: "部分可用",
  BLOCKED: "不可用",
  EXPIRING: "即将过期",
  REAUTH_REQUIRED: "需重新授权",
  SCOPE_MISSING: "权限不足",
  RATE_LIMITED: "限流",
  WEBHOOK_FAILED: "Webhook 异常",
  DISABLED: "已停用",
  DRAFT: "草稿",
  DONE: "已完成",
  INFO: "信息",
};

const tones: Record<string, string> = {
  HEALTHY: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  FRESH: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  COMPLETE: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  WARNING: "border-amber-500/25 bg-amber-500/10 text-amber-400",
  DELAYED: "border-amber-500/25 bg-amber-500/10 text-amber-400",
  PARTIAL: "border-amber-500/25 bg-amber-500/10 text-amber-400",
  AT_RISK: "border-orange-500/25 bg-orange-500/10 text-orange-400",
  STALE: "border-orange-500/25 bg-orange-500/10 text-orange-400",
  CRITICAL: "border-rose-500/25 bg-rose-500/10 text-rose-400",
  BLOCKED: "border-rose-500/25 bg-rose-500/10 text-rose-400",
  UNKNOWN: "border-slate-600 bg-slate-800/70 text-slate-400",
  EXPIRING: "border-amber-500/25 bg-amber-500/10 text-amber-400",
  REAUTH_REQUIRED: "border-rose-500/25 bg-rose-500/10 text-rose-400",
  SCOPE_MISSING: "border-orange-500/25 bg-orange-500/10 text-orange-400",
  RATE_LIMITED: "border-amber-500/25 bg-amber-500/10 text-amber-400",
  WEBHOOK_FAILED: "border-orange-500/25 bg-orange-500/10 text-orange-400",
  DISABLED: "border-slate-600 bg-slate-800/70 text-slate-400",
  DRAFT: "border-sky-500/25 bg-sky-500/10 text-sky-400",
  DONE: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  INFO: "border-sky-500/25 bg-sky-500/10 text-sky-400",
};

export function HealthStatusBadge({ value, compact = false }: { value?: unknown; compact?: boolean }) {
  const normalized = String(value || "UNKNOWN").toUpperCase();
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full border font-medium ${compact ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs"} ${tones[normalized] ?? tones.UNKNOWN}`}>
      {labels[normalized] ?? normalized}
    </span>
  );
}
