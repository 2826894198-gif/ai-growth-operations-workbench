import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";

export function Experiments() {
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setItems(await api.experiments());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">实验</h1>
      <Section title="实验列表">
        {items.length === 0 ? (
          <p className="py-4 text-sm text-slate-500">暂无实验。通过 POST /api/v1/experiments 创建。</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {items.map((experiment) => (
              <div key={String(experiment.id)} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <p className="font-medium text-slate-200">{String(experiment.name)}</p>
                <p className="mt-1 text-xs text-slate-400">{String(experiment.hypothesis ?? "—")}</p>
                <p className="mt-2 text-xs text-slate-500">
                  状态：{String(experiment.status)} · 指标：{String(experiment.primary_metric ?? "—")}
                </p>
                {experiment.protected_by_rule ? (
                  <p className="mt-1 text-xs text-sky-400">Protected by Experiment</p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
