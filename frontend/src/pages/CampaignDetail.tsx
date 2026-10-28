import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";
import { SeverityBadge } from "../components/status/SeverityBadge";

export function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      setData(await api.adsCampaign(id));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Spinner />;
  if (!data) return <p className="text-slate-400">未找到 Campaign。</p>;

  const recs = (data.recommendations as Array<Record<string, unknown>>) ?? [];
  const groups = (data.ad_groups as Array<Record<string, unknown>>) ?? [];

  return (
    <div className="space-y-6">
      <Link to="/ads" className="text-sm text-sky-300 hover:text-sky-200">
        ← Ads
      </Link>
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">{String(data.name)}</h1>
        <p className="mt-1 text-sm text-slate-400">
          {String(data.platform)} · {String(data.status)} · {String(data.objective ?? "—")}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <DetailStat label="花费" value={`$${Number(data.spend ?? 0).toFixed(2)}`} />
        <DetailStat label="转化" value={String(data.conversions ?? 0)} />
        <DetailStat label="Ad Groups" value={String(groups.length)} />
        <DetailStat label="推荐" value={String(recs.length)} />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section title="推荐建议">
          {recs.length === 0 ? (
            <p className="py-3 text-sm text-slate-500">暂无推荐。</p>
          ) : (
            <div className="space-y-2">
              {recs.map((rec) => (
                <div key={String(rec.id)} className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm">
                  <SeverityBadge value={String(rec.severity)} />
                  <span className="text-slate-300">{String(rec.primary_action)}</span>
                  <span className="text-slate-500">{String(rec.reason_group)}</span>
                  <span className="ml-auto text-xs text-slate-500">{Number(rec.confidence ?? 0).toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section title="广告组结构">
          <div className="space-y-1 text-sm">
            {groups.map((group) => (
              <div key={String(group.id)} className="flex justify-between border-b border-slate-800/60 py-1.5">
                <span className="text-slate-300">{String(group.name)}</span>
                <span className="text-slate-500">{String(group.status)}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}

function DetailStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-slate-100">{value}</p>
    </div>
  );
}
