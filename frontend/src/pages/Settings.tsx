import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";

export function Settings() {
  const [targets, setTargets] = useState<Array<Record<string, unknown>>>([]);
  const [rules, setRules] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [targetData, ruleData] = await Promise.all([api.settingsTargets(), api.rules()]);
      setTargets(targetData);
      setRules(ruleData);
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
      <h1 className="text-2xl font-semibold text-slate-100">设置</h1>

      <Section title="业务目标">
        {targets.length === 0 ? (
          <p className="py-3 text-sm text-slate-500">暂无业务目标配置。</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {targets.map((target) => (
              <div key={String(target.id)} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm">
                <p className="font-medium text-slate-200">{String(target.name)}</p>
                <p className="mt-1 text-xs text-slate-400">作用域：{String(target.scope_type)}</p>
                <div className="mt-2 space-y-1 text-xs text-slate-500">
                  <p>Target CPA: {target.target_cpa != null ? `$${Number(target.target_cpa).toFixed(2)}` : "—"}</p>
                  <p>Target ROAS: {target.target_roas != null ? Number(target.target_roas).toFixed(2) : "—"}</p>
                  <p>Break-even ROAS: {target.break_even_roas != null ? Number(target.break_even_roas).toFixed(2) : "—"}</p>
                  <p>日花费上限: {target.max_daily_spend != null ? `$${Number(target.max_daily_spend).toFixed(0)}` : "—"}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="规则">
        <div className="max-h-96 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs uppercase text-slate-500">
                <th className="py-2 pr-2">规则</th>
                <th className="py-2 pr-2">状态</th>
                <th className="py-2 pr-2">版本</th>
                <th className="py-2">冷却（分钟）</th>
              </tr>
            </thead>
            <tbody>
              {rules.slice(0, 50).map((rule) => (
                <tr key={String(rule.rule_key)} className="border-b border-slate-800/60">
                  <td className="py-2 pr-2 text-slate-200">{String(rule.rule_key)}</td>
                  <td className="py-2 pr-2 text-slate-400">{String(rule.status)}</td>
                  <td className="py-2 pr-2 text-slate-400">v{String(rule.version)}</td>
                  <td className="py-2 text-slate-400">{String(rule.cooldown_minutes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
