import type { ReactNode } from "react";

interface SectionProps {
  title: string;
  children: ReactNode;
}

export function Section({ title, children }: SectionProps) {
  return (
    <section className="min-w-0 rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">{title}</h2>
      {children}
    </section>
  );
}
