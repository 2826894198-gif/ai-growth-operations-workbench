import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { EmptyState } from "../components/common/EmptyState";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";

export function Competitors() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setData(await api.competitors());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Spinner />;
  if (!data) return <p className="text-slate-400">加载失败</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">竞品</h1>
      <Section title="观察清单">
        {data.enabled ? (
          <EmptyState title="暂无竞品观察" hint="通过 AI 竞品研究添加公开页面" />
        ) : (
          <EmptyState title="竞品研究未启用" hint="在 Settings → AI 中开启 AI_BROWSER_RESEARCH_ENABLED（仅公开只读研究）" />
        )}
      </Section>
      <p className="text-xs text-slate-500">所有结论仅为公开样本观察，不代表市场总体事实。</p>
    </div>
  );
}
