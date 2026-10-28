import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { TrendChart } from "../components/charts/TrendChart";
import { PartialDataBanner } from "../components/common/PartialDataBanner";
import { KpiCard } from "../components/kpi/KpiCard";
import { RecommendationCard } from "../components/recommendation/RecommendationCard";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";
import { StatusBadge } from "../components/status/StatusBadge";
import type { DashboardOverview } from "../domain/types";

export function Overview() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setData((await api.dashboardOverview()) as unknown as DashboardOverview);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Spinner />;
  if (!data) return <p className="text-slate-400">加载失败</p>;

  const brief = data.daily_brief;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold text-slate-100">经营概览</h1>
        <StatusBadge value={data.business_status} />
      </div>
      <PartialDataBanner sources={[]} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {data.kpis.map((kpi) => (
          <KpiCard key={kpi.key} kpi={kpi} />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Section title="优先推荐">
          <div className="space-y-3">
            {data.recommendations.length === 0 ? (
              <p className="py-4 text-sm text-slate-500">暂无开放推荐。</p>
            ) : (
              data.recommendations.map((rec) => (
                <RecommendationCard
                  key={rec.id}
                  id={rec.id}
                  entityType={rec.entity_type}
                  entityId={rec.entity_id}
                  action={rec.primary_action}
                  reason={rec.reason_group}
                  severity={rec.severity}
                  confidence={rec.confidence}
                  evidence={rec.evidence}
                />
              ))
            )}
          </div>
        </Section>

        <Section title="平台表现">
          <div className="space-y-3">
            {data.platforms.map((platform) => (
              <div key={String(platform.platform)} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm">
                <div className="flex justify-between">
                  <span className="font-medium text-slate-200">{String(platform.platform)}</span>
                  <span className="text-slate-400">花费 ${Number(platform.spend ?? 0).toFixed(2)}</span>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-slate-400">
                  <span>展示 {Number(platform.impressions ?? 0).toLocaleString()}</span>
                  <span>点击 {Number(platform.clicks ?? 0).toLocaleString()}</span>
                  <span>平台 ROAS {platform.platform_roas != null ? Number(platform.platform_roas).toFixed(2) : "—"}</span>
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section title="AI 今日简报">
          {brief.available ? (
            <div className="space-y-3 text-sm">
              <p className="text-slate-200">{String(brief.executive_summary)}</p>
              <div>
                <p className="text-xs uppercase tracking-wider text-slate-500">今日行动</p>
                <ul className="mt-1 space-y-1 text-slate-300">
                  {((brief.actions_now as string[] | undefined) ?? []).map((action, index) => (
                    <li key={index}>· {action}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-slate-500">不要动</p>
                <ul className="mt-1 space-y-1 text-slate-400">
                  {((brief.do_not_change as string[] | undefined) ?? []).map((item, index) => (
                    <li key={index}>· {item}</li>
                  ))}
                </ul>
              </div>
              <p className="text-xs text-slate-500">来源：AI · 置信度 {Number(brief.confidence ?? 0).toFixed(2)}</p>
            </div>
          ) : (
            <p className="py-4 text-sm text-slate-500">{String(brief.message ?? "暂无简报")}</p>
          )}
        </Section>
      </div>

      <Section title="趋势（近 7 天）">
        <div className="grid gap-4 lg:grid-cols-3">
          <TrendChart data={data.trend} metric="spend" />
          <TrendChart data={data.trend} metric="net_revenue" />
          <TrendChart data={data.trend} metric="blended_roas" />
        </div>
      </Section>
    </div>
  );
}
