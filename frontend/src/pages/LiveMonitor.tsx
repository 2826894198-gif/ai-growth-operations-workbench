import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";
import { SeverityBadge } from "../components/status/SeverityBadge";

export function LiveMonitor() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setData(await api.dashboardLive());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 60000);
    return () => clearInterval(timer);
  }, [load]);

  if (loading) return <Spinner />;
  if (!data) return <p className="text-slate-400">加载失败</p>;

  const today = (data.today as Record<string, unknown>) ?? {};
  const campaigns = (data.campaigns as Array<Record<string, unknown>>) ?? [];
  const timeline = (data.timeline as Array<Record<string, unknown>>) ?? [];
  const alerts = (data.alerts as Array<Record<string, unknown>>) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold text-slate-100">实时监控</h1>
        <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300">
          日内数据为临时值
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <LiveStat label="今日花费" value={`$${Number(today.spend ?? 0).toFixed(2)}`} />
        <LiveStat label="今日订单" value={String(today.orders ?? 0)} />
        <LiveStat label="今日净收入" value={`$${Number(today.net_revenue ?? 0).toFixed(2)}`} />
        <LiveStat label="今日混合 ROAS" value={today.blended_roas != null ? Number(today.blended_roas).toFixed(2) : "—"} />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section title="高优先级告警">
          {alerts.length === 0 ? (
            <p className="py-3 text-sm text-slate-500">暂无高优告警。</p>
          ) : (
            <div className="space-y-2">
              {alerts.map((alert) => (
                <div key={String(alert.id)} className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm">
                  <SeverityBadge value={String(alert.severity)} />
                  <span className="text-slate-300">{String(alert.message)}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section title="事件时间线">
          {timeline.length === 0 ? (
            <p className="py-3 text-sm text-slate-500">暂无事件。</p>
          ) : (
            <div className="space-y-1 text-sm">
              {timeline.slice(0, 10).map((event, index) => (
                <div key={index} className="flex justify-between border-b border-slate-800/60 py-1">
                  <span className="text-slate-300">{String(event.rule)}</span>
                  <span className="text-xs text-slate-500">
                    {String(event.result)} · {event.time ? new Date(String(event.time)).toLocaleTimeString() : "—"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>

      <Section title="Campaign 实时表">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs uppercase text-slate-500">
                <th className="py-2 pr-2">Campaign</th>
                <th className="py-2 pr-2">平台</th>
                <th className="py-2 pr-2">花费</th>
                <th className="py-2">转化</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((campaign) => (
                <tr key={String(campaign.campaign_id)} className="border-b border-slate-800/60">
                  <td className="py-2 pr-2 text-slate-200">{String(campaign.campaign_id)}</td>
                  <td className="py-2 pr-2 text-slate-400">{String(campaign.platform)}</td>
                  <td className="py-2 pr-2 tabular-nums text-slate-300">${Number(campaign.spend ?? 0).toFixed(2)}</td>
                  <td className="py-2 tabular-nums text-slate-300">{Number(campaign.conversions ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

function LiveStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">{value}</p>
    </div>
  );
}
