import type { ReactNode } from "react";

export function EntitySummary({
  title,
  subtitle,
  avatar,
  actions,
  meta,
}: {
  title: string;
  subtitle?: string;
  avatar?: ReactNode;
  actions?: ReactNode;
  meta?: Array<{ label: string; value: string }>;
}) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      {avatar ? <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-700 text-base text-slate-100">{avatar}</div> : null}
      <div className="min-w-0">
        <h2 className="truncate text-lg font-semibold text-slate-100">{title}</h2>
        {subtitle ? <p className="text-xs text-slate-500">{subtitle}</p> : null}
      </div>
      {meta?.length ? (
        <div className="flex flex-wrap gap-3 text-xs text-slate-400">
          {meta.map((item) => (
            <span key={item.label}>
              {item.label}: <span className="text-slate-200">{item.value}</span>
            </span>
          ))}
        </div>
      ) : null}
      {actions ? <div className="ml-auto flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}
