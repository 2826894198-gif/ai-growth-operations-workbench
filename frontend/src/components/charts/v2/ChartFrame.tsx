import type { ReactNode } from "react";
import type { ChartQuality, ChartStatus } from "./chartTypes";

const STATUS_COPY: Record<ChartStatus, { label: string; detail: string }> = {
  loading: { label: "正在加载数据", detail: "正在读取当前范围的指标。" },
  empty: { label: "当前范围暂无数据", detail: "请先连接账号并完成一次同步。" },
  partial: { label: "数据不完整", detail: "图表只显示已同步的部分数据。" },
  stale: { label: "数据可能已过期", detail: "请检查同步状态后再做判断。" },
  not_connected: { label: "数据源未连接", detail: "连接数据源后，这个图表会自动显示。" },
  error: { label: "图表暂时无法加载", detail: "可以重试；如果持续失败，请检查数据源状态。" },
  ready: { label: "", detail: "" },
};

export function ChartFrame({
  title,
  subtitle,
  quality,
  children,
  className = "",
  onRetry,
  actions,
}: {
  title: string;
  subtitle?: string;
  quality?: ChartQuality;
  children: ReactNode;
  className?: string;
  onRetry?: () => void;
  actions?: ReactNode;
}) {
  const status = quality?.status ?? "ready";
  const statusCopy = STATUS_COPY[status];
  const isBlocked = status !== "ready";

  return (
    <section className={`min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5 ${className}`}>
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-slate-200">{title}</h2>
          {subtitle ? <p className="mt-1 text-[10px] leading-relaxed text-slate-500">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </header>

      <div className="mt-4 min-h-[16rem]">
        {isBlocked ? (
          <div
            className="flex min-h-[16rem] flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-950/30 px-5 text-center"
            role={status === "error" ? "alert" : "status"}
          >
            {status === "loading" ? <span className="mb-3 h-6 w-6 animate-spin rounded-full border-2 border-slate-700 border-t-sky-400" /> : null}
            <p className="text-sm font-medium text-slate-300">{statusCopy.label}</p>
            <p className="mt-1 max-w-sm text-xs leading-relaxed text-slate-500">{quality?.error || quality?.caveat || statusCopy.detail}</p>
            {onRetry && status === "error" ? <button type="button" onClick={onRetry} className="mt-4 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:border-sky-500 hover:text-sky-300">重试</button> : null}
          </div>
        ) : children}
      </div>

      {quality && (quality.source || quality.freshness || quality.sampleSize != null || quality.comparableSampleSize != null || quality.caveat) ? (
        <footer className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-800 pt-3 text-[10px] leading-relaxed text-slate-600">
          {quality.source ? <span>来源：{quality.source}</span> : null}
          {quality.freshness ? <span>更新：{quality.freshness}</span> : null}
          {quality.sampleSize != null ? <span>样本：{quality.sampleSize.toLocaleString("zh-CN")}</span> : null}
          {quality.comparableSampleSize != null ? <span>可比较：{quality.comparableSampleSize.toLocaleString("zh-CN")}</span> : null}
          {quality.caveat ? <span>{quality.caveat}</span> : null}
        </footer>
      ) : null}
    </section>
  );
}
