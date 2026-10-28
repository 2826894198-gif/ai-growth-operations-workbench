import { Link } from "react-router-dom";

function formatTime(value?: unknown) {
  if (!value) return "尚未计算";
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
}

export function DataBoundaryBanner({
  dataMode,
  dataUsable,
  evaluatedAt,
  blockingReasons = [],
}: {
  dataMode?: unknown;
  dataUsable?: boolean;
  evaluatedAt?: unknown;
  blockingReasons?: unknown[];
}) {
  const demo = String(dataMode || "MOCK").toUpperCase() === "MOCK";
  const blocked = dataUsable === false;
  return (
    <div className={`flex flex-col gap-3 rounded-xl border px-4 py-3 sm:flex-row sm:items-center sm:justify-between ${blocked ? "border-amber-500/25 bg-amber-500/10" : "border-slate-800 bg-slate-900/50"}`}>
      <div className="flex min-w-0 items-start gap-3">
        <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${blocked ? "bg-amber-400" : "bg-emerald-400"}`} />
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-200">
            {blocked ? "当前数据不足以支持确定经营结论" : "当前数据可用于复盘"}
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
            {demo ? "演示环境 · 数据仅用于流程验证" : "真实读取环境"} · 最近评估 {formatTime(evaluatedAt)}
            {blockingReasons.length ? ` · 阻塞项：${blockingReasons.slice(0, 3).join("、")}` : ""}
          </p>
        </div>
      </div>
      {blocked ? <Link to="/data-health" className="shrink-0 text-xs font-medium text-amber-400 hover:text-amber-300">查看数据健康 →</Link> : null}
    </div>
  );
}
