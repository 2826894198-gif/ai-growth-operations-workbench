import type { Alert } from "../types";

interface AlertBannerProps {
  alerts: Alert[];
}

export function AlertBanner({ alerts }: AlertBannerProps) {
  if (alerts.length === 0) {
    return (
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-300">
        暂无环境告警，系统运行正常。
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {alerts.map((alert, index) => (
        <div
          key={`${alert.code}-${index}`}
          className={`rounded-xl border px-4 py-3 text-sm ${
            alert.severity === "CRITICAL"
              ? "border-rose-500/30 bg-rose-500/10 text-rose-200"
              : "border-amber-500/30 bg-amber-500/10 text-amber-200"
          }`}
        >
          <span className="mr-2 font-semibold uppercase tracking-wider text-xs">{alert.severity}</span>
          {alert.message}
        </div>
      ))}
    </div>
  );
}
