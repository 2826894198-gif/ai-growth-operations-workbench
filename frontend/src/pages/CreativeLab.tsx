import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { EmptyState } from "../components/common/EmptyState";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";

export function CreativeLab() {
  const [creatives, setCreatives] = useState<Array<Record<string, unknown>>>([]);
  const [briefs, setBriefs] = useState<Array<Record<string, unknown>>>([]);
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [creativeData, briefData] = await Promise.all([api.creatives(), api.creativeBriefs()]);
      setCreatives(creativeData);
      setBriefs(briefData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openCreative = async (id: string) => {
    setSelected(await api.creative(id));
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">Creative Lab</h1>

      <Section title="素材库">
        {creatives.length === 0 ? (
          <EmptyState title="暂无素材数据" hint="先同步 Meta creatives，再执行 make ai-analyze-creative" />
        ) : (
          <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-4">
            {creatives.map((creative) => (
              <button
                key={String(creative.creative_id)}
                onClick={() => void openCreative(String(creative.creative_id))}
                className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-left hover:border-slate-600"
              >
                <div className="aspect-video rounded-lg bg-slate-950" />
                <p className="mt-2 truncate text-sm font-medium text-slate-200">{String(creative.title ?? creative.name ?? creative.creative_id)}</p>
                <p className="mt-1 text-xs text-slate-500">
                  花费 ${Number(creative.spend_30d ?? 0).toFixed(2)} · 购买 {Number(creative.purchases_30d ?? 0)}
                </p>
              </button>
            ))}
          </div>
        )}
      </Section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section title="素材详情">
          {selected ? (
            <div className="space-y-2 text-sm">
              <p className="text-lg font-medium text-slate-100">{String(selected.title ?? selected.name)}</p>
              <p className="text-slate-400">{String(selected.body ?? "—")}</p>
              <p className="text-xs text-slate-500">CTA: {String(selected.cta_type ?? "—")} · 落地页: {String(selected.landing_page_url ?? "—")}</p>
              {(selected.ai_analyses as Array<Record<string, unknown>> ?? []).length > 0 ? (
                <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                  <p className="text-xs uppercase tracking-wider text-slate-500">Creative DNA</p>
                  <pre className="mt-2 max-h-56 overflow-auto text-xs text-slate-300">
                    {JSON.stringify((selected.ai_analyses as Array<Record<string, unknown>>)[0].creative_dna, null, 2)}
                  </pre>
                </div>
              ) : (
                <p className="text-xs text-slate-500">暂无 AI 分析。执行 make ai-analyze-creative CREATIVE_ID=…</p>
              )}
            </div>
          ) : (
            <p className="py-4 text-sm text-slate-500">点击左侧素材查看详情与 Creative DNA。</p>
          )}
        </Section>

        <Section title="创意 Brief">
          {briefs.length === 0 ? (
            <EmptyState title="暂无创意 Brief" hint="Brief 由 Strategy Agent 生成或通过 POST /creative-briefs 创建" />
          ) : (
            <div className="space-y-2">
              {briefs.map((brief) => (
                <div key={String(brief.id)} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm">
                  <p className="font-medium text-slate-200">{String(brief.title)}</p>
                  <p className="mt-1 text-xs text-slate-400">{String(brief.objective ?? "—")}</p>
                  <p className="mt-1 text-xs text-slate-500">状态：{String(brief.status)}</p>
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}
