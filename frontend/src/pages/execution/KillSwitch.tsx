import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import { Section } from "../../components/Section";
import { Spinner } from "../../components/Spinner";

export function KillSwitch() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [switches, setSwitches] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [healthData, switchData] = await Promise.all([api.executionHealth(), api.killSwitches()]);
      setHealth(healthData);
      setSwitches(switchData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = async (enabled: boolean) => {
    if (enabled) await api.enableGlobalKillSwitch();
    else await api.disableGlobalKillSwitch();
    await load();
  };

  if (loading && !health) return <Spinner />;

  const active = Boolean(health?.global_kill_switch);
  const last24 = (health?.last_24h ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-6">
      <div
        className={`rounded-xl border p-5 ${active ? "border-rose-700 bg-rose-950/40" : "border-emerald-800 bg-emerald-950/30"}`}
      >
        <div className="flex items-center justify-between">
          <div>
            <p className={`text-lg font-semibold ${active ? "text-rose-300" : "text-emerald-300"}`}>
              {active ? "EXECUTION KILL SWITCH ACTIVE" : "执行已启用"}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              模式 {String(health?.execution_mode ?? "manual")} · 执行开关 {String(health?.execution_enabled)} · 全局熔断 {String(active)}
            </p>
          </div>
          <button
            onClick={() => void toggle(!active)}
            className={`rounded-lg border px-4 py-2 text-sm ${active ? "border-emerald-700 text-emerald-300" : "border-rose-700 text-rose-300"}`}
          >
            {active ? "解除熔断（二次确认）" : "紧急停止"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Section title="24h 任务">
          <p className="text-2xl font-semibold text-slate-100">{String(last24.total ?? 0)}</p>
          <p className="text-[10px] text-slate-500">成功 {String(last24.succeeded ?? 0)} · 失败 {String(last24.failed ?? 0)}</p>
        </Section>
        <Section title="未知结果">
          <p className="text-2xl font-semibold text-amber-300">{String(last24.unknown_outcomes ?? 0)}</p>
        </Section>
        <Section title="验证失败">
          <p className="text-2xl font-semibold text-rose-300">{String(last24.verification_failures ?? 0)}</p>
        </Section>
        <Section title="待审批">
          <p className="text-2xl font-semibold text-sky-300">{String(health?.pending_approvals ?? 0)}</p>
        </Section>
      </div>

      <Section title="熔断开关记录">
        <div className="space-y-2">
          {((switches?.all as Array<Record<string, unknown>>) ?? []).map((item) => (
            <div key={String(item.id)} className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2 text-xs">
              <span className="text-slate-200">
                {String(item.scope_type)} {String(item.scope_id ?? "")} · {String(item.enabled)}
              </span>
              <span className="text-slate-500">{String(item.reason ?? "")}</span>
            </div>
          ))}
          {!switches?.all || (switches.all as unknown[]).length === 0 ? <p className="py-2 text-sm text-slate-500">暂无熔断记录。</p> : null}
        </div>
      </Section>
    </div>
  );
}
