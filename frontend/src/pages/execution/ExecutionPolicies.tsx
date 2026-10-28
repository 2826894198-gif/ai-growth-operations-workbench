import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import { Section } from "../../components/Section";
import { Spinner } from "../../components/Spinner";

export function ExecutionPolicies() {
  const [policies, setPolicies] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setPolicies(await api.executionPolicies());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const seed = async () => {
    await api.seedExecutionPolicies();
    await load();
  };

  if (loading && !policies.length) return <Spinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">执行策略</h1>
          <p className="text-xs text-slate-500">MODE_1_MANUAL 为默认；Guarded Auto 仅框架保留且默认关闭。</p>
        </div>
        <button onClick={() => void seed()} className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300">
          载入默认策略
        </button>
      </div>
      <Section title="策略列表">
        <div className="space-y-2">
          {policies.map((policy) => (
            <div key={String(policy.id)} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-200">
                  {String(policy.action_type)} · v{String(policy.version)}
                </p>
                <span className={`text-[10px] ${policy.enabled ? "text-emerald-400" : "text-rose-400"}`}>{String(policy.enabled)}</span>
              </div>
              <p className="mt-1 text-[10px] text-slate-500">
                模式 {String(policy.mode)} · 最大风险 {String(policy.max_risk_level)} · 最低置信度 {Number(policy.min_confidence)} · 最大变更 {String(policy.max_change_pct ?? "—")}% ·
                冷却 {String(policy.cooldown_minutes)}m · 每小时 {String(policy.max_actions_per_hour)} / 每天 {String(policy.max_actions_per_day)}
              </p>
            </div>
          ))}
          {policies.length === 0 ? (
            <p className="py-3 text-sm text-slate-500">
              暂无策略。点击“载入默认策略”，或运行 <code className="text-sky-400">make smoke-execution</code>。
            </p>
          ) : null}
        </div>
      </Section>
    </div>
  );
}
