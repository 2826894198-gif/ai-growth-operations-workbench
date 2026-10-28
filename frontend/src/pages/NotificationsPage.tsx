import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";
import { SeverityBadge } from "../components/status/SeverityBadge";

export function NotificationsPage() {
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setItems(await api.notifications());
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
      <h1 className="text-2xl font-semibold text-slate-100">通知</h1>
      <Section title="通知中心">
        {items.length === 0 ? (
          <p className="py-4 text-sm text-slate-500">暂无通知。</p>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <div key={String(item.id)} className="flex items-start gap-3 rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm">
                <SeverityBadge value={String(item.severity)} />
                <div>
                  <p className="text-slate-200">{String(item.title)}</p>
                  <p className="text-xs text-slate-500">{String(item.body ?? "")}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
