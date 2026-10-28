import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useScope } from "../domain/scope";
import { Section } from "../components/Section";
import { StatCard } from "../components/StatCard";
import { Spinner } from "../components/Spinner";

export function FocusMonitors() {
  const { scope, accounts } = useScope();
  const [monitors, setMonitors] = useState<Array<Record<string, unknown>>>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [watchlists, setWatchlists] = useState<Array<Record<string, unknown>>>([]);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rows, lists] = await Promise.all([api.focusMonitors(scope.workspaceId), api.watchlists(scope.workspaceId)]);
      setMonitors(rows);
      setWatchlists(lists);
      if (!activeId && rows.length) setActiveId(String(rows[0].id));
    } finally {
      setLoading(false);
    }
  }, [scope.workspaceId, activeId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!activeId) return;
    void api.focusMonitor(activeId, 7).then(setDetail);
  }, [activeId]);

  const create = async () => {
    const account = accounts[0];
    if (!account) return;
    await api.createFocusMonitor({
      workspace_id: scope.workspaceId,
      scope_type: "ACCOUNT",
      scope_id: String(account.id),
      name: name || `重点监控 @${String(account.username)}`,
      priority: "WATCH",
      refresh_interval_minutes: 15,
      actor: "operator",
    });
    setName("");
    setActiveId(null);
    await load();
  };

  const stop = async (id: string) => {
    await api.stopFocusMonitor(id);
    setActiveId(null);
    await load();
  };

  if (loading && !monitors.length) return <Spinner />;

  const monitorHeader = (detail?.monitor ?? {}) as Record<string, unknown>;
  const organic = (detail?.organic ?? {}) as Record<string, unknown>;
  const paid = (detail?.paid ?? {}) as Record<string, unknown>;
  const alerts = (detail?.alerts ?? []) as Array<Record<string, unknown>>;
  const events = (detail?.execution_events ?? []) as Array<Record<string, unknown>>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">重点监控</h1>
          <p className="text-xs text-slate-500">What I need to watch now — 复用 PART 03 规则与 PART 06 执行，不重复造规则引擎。</p>
        </div>
        <div className="flex gap-2">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="监控名称"
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200"
          />
          <button onClick={() => void create()} className="rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-1.5 text-xs text-amber-300">
            + 创建账号监控
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Section title={`监控列表（${monitors.length}）`}>
          <div className="space-y-2">
            {monitors.map((monitor) => (
              <button
                key={String(monitor.id)}
                onClick={() => setActiveId(String(monitor.id))}
                className={`w-full rounded-lg border px-3 py-2 text-left ${
                  activeId === String(monitor.id) ? "border-amber-700 bg-amber-950/30" : "border-slate-800 bg-slate-900/40"
                }`}
              >
                <p className="text-sm text-slate-200">{String(monitor.name)}</p>
                <p className="text-[10px] text-slate-500">
                  {String(monitor.scope_type)} · {String(monitor.priority)} · 每 {String(monitor.refresh_interval_minutes)} 分钟
                </p>
              </button>
            ))}
            {monitors.length === 0 ? <p className="py-3 text-sm text-slate-500">暂无重点监控。</p> : null}
          </div>
          <div className="mt-4">
            <p className="mb-2 text-xs font-medium text-slate-400">关注清单</p>
            {watchlists.map((list) => (
              <div key={String(list.id)} className="mb-2 rounded-lg border border-slate-800 bg-slate-900/40 p-2 text-xs text-slate-400">
                <p className="font-medium text-slate-300">{String(list.name)}</p>
                <p className="text-[10px]">{Array.isArray(list.items) ? `${(list.items as unknown[]).length} 项` : "0 项"}</p>
              </div>
            ))}
          </div>
        </Section>

        <div className="space-y-6 lg:col-span-2">
          {detail ? (
            <>
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-amber-300">FOCUSING</p>
                    <h2 className="text-lg font-semibold text-slate-100">{String(monitorHeader.name ?? "")}</h2>
                    <p className="text-[10px] text-slate-500">
                      {String(monitorHeader.scope_type)} · {String(monitorHeader.scope_id)} · 基准策略 {String(monitorHeader.baseline_strategy)}
                    </p>
                  </div>
                  <button onClick={() => void stop(String(activeId))} className="rounded-lg border border-rose-700 px-3 py-1.5 text-xs text-rose-300">
                    停止监控
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <StatCard label="自然浏览" value={Number(organic.views || 0)} />
                <StatCard label="付费花费" value={Number(paid.spend || 0)} />
                <StatCard label="付费 ROAS" value={Number(paid.roas || 0)} />
                <StatCard label="日浏览速度" value={Number((detail.velocity as Record<string, unknown> | undefined)?.views_per_day || 0)} />
              </div>
              <Section title="规则告警（PART 03 推荐）">
                <div className="space-y-2">
                  {alerts.map((alert) => (
                    <div key={String(alert.recommendation_id)} className="rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2 text-xs">
                      <span className="text-slate-200">{String(alert.primary_action)}</span>
                      <span className="ml-2 text-slate-500">{String(alert.severity)} · 置信度 {Number(alert.confidence).toFixed(2)}</span>
                    </div>
                  ))}
                  {alerts.length === 0 ? <p className="py-2 text-sm text-slate-500">当前无规则告警。</p> : null}
                </div>
              </Section>
              <Section title="执行事件（PART 06）">
                <div className="space-y-1">
                  {events.map((event) => (
                    <div key={String(event.job_id)} className="flex justify-between rounded border border-slate-800 bg-slate-900/30 px-3 py-1.5 text-xs">
                      <span className="text-slate-300">{String(event.action_type)}</span>
                      <span className="text-slate-500">{String(event.status)} {String(event.created_at ?? "")}</span>
                    </div>
                  ))}
                  {events.length === 0 ? <p className="py-2 text-sm text-slate-500">暂无执行事件。</p> : null}
                </div>
              </Section>
            </>
          ) : (
            <p className="py-10 text-sm text-slate-500">选择一个监控查看详情。</p>
          )}
        </div>
      </div>
    </div>
  );
}
