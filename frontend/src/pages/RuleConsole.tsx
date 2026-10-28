import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";

interface Rule {
  rule_key: string;
  name: string;
  category: string;
  platform?: string | null;
  status: string;
  severity: string;
  version: number;
}

interface Recommendation {
  id: string;
  entity_type: string;
  entity_id: string;
  platform?: string | null;
  primary_action: string;
  reason_group: string;
  severity: string;
  confidence: number;
  status: string;
}

export function RuleConsole() {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [rules, setRules] = useState<Rule[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [simRule, setSimRule] = useState("META_NO_PURCHASE_BURN");
  const [simParam, setSimParam] = useState("multiple=1.5");
  const [simResult, setSimResult] = useState<Record<string, unknown> | null>(null);
  const [simBusy, setSimBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [healthData, ruleData, recData] = await Promise.all([
        api.ruleHealth(),
        api.rules(),
        api.recommendations(),
      ]);
      setHealth(healthData);
      setRules(ruleData as unknown as Rule[]);
      setRecommendations(recData as unknown as Recommendation[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runSimulation = async () => {
    setSimBusy(true);
    setSimResult(null);
    try {
      const [key, value] = simParam.split("=");
      const end = new Date().toISOString().slice(0, 10);
      const start = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10);
      const numeric = Number(value);
      const result = await api.simulateRule(simRule, { [key]: Number.isNaN(numeric) ? value : numeric }, start, end);
      setSimResult(result);
    } finally {
      setSimBusy(false);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="规则引擎控制台"
        subtitle="增长规则引擎 · 确定性推荐 · 影子模式"
        actions={
          <div className="flex gap-2">
            <Link
              to="/ai-console"
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
            >
              AI 智能
            </Link>
            <Link
              to="/data-health"
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
            >
              ← 数据健康
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="启用规则" value={String(health.active_rules ?? 0)} />
        <Stat label="影子规则" value={String(health.shadow_rules ?? 0)} />
        <Stat label="开放推荐" value={String(health.open_recommendations ?? 0)} />
        <Stat label="高风险" value={String(health.high_severity ?? 0)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="推荐建议">
          {recommendations.length === 0 ? (
            <p className="py-3 text-sm text-slate-500">
              暂无推荐。先执行 make rules-load 和 make rules-evaluate 生成推荐。
            </p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-2">对象</th>
                  <th className="py-2 pr-2">动作</th>
                  <th className="py-2 pr-2">原因</th>
                  <th className="py-2 pr-2">级别</th>
                  <th className="py-2 pr-2">置信度</th>
                  <th className="py-2">状态</th>
                </tr>
              </thead>
              <tbody>
                {recommendations.slice(0, 15).map((rec) => (
                  <tr key={rec.id} className="border-b border-slate-800/60">
                    <td className="py-2 pr-2 text-slate-300">{rec.entity_id.slice(0, 24)}</td>
                    <td className="py-2 pr-2 text-slate-200">{rec.primary_action}</td>
                    <td className="py-2 pr-2 text-slate-400">{rec.reason_group}</td>
                    <td className="py-2 pr-2">
                      <Badge value={rec.severity} />
                    </td>
                    <td className="py-2 pr-2 text-slate-300">{rec.confidence.toFixed(2)}</td>
                    <td className="py-2">
                      <Badge value={rec.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>

        <Section title="规则列表">
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-2">规则</th>
                  <th className="py-2 pr-2">分类</th>
                  <th className="py-2 pr-2">级别</th>
                  <th className="py-2">状态</th>
                </tr>
              </thead>
              <tbody>
                {rules.slice(0, 25).map((rule) => (
                  <tr key={`${rule.rule_key}-${rule.version}`} className="border-b border-slate-800/60">
                    <td className="py-2 pr-2 text-slate-200">{rule.rule_key}</td>
                    <td className="py-2 pr-2 text-slate-400">{rule.category}</td>
                    <td className="py-2 pr-2">
                      <Badge value={rule.severity} />
                    </td>
                    <td className="py-2">
                      <Badge value={rule.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      </div>

      <Section title="规则模拟">
        <div className="flex flex-wrap items-end gap-3">
          <label className="block text-xs uppercase tracking-wider text-slate-500">
            规则
            <input
              value={simRule}
              onChange={(event) => setSimRule(event.target.value)}
              className="mt-1 block w-72 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
            />
          </label>
          <label className="block text-xs uppercase tracking-wider text-slate-500">
            参数（键=值）
            <input
              value={simParam}
              onChange={(event) => setSimParam(event.target.value)}
              className="mt-1 block w-56 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
            />
          </label>
          <button
            onClick={() => void runSimulation()}
            disabled={simBusy}
            className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:border-slate-500 disabled:opacity-40"
          >
            {simBusy ? "运行中…" : "模拟最近 30 天"}
          </button>
        </div>
        {simResult ? (
          <pre className="mt-4 max-h-64 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
            {JSON.stringify(simResult, null, 2)}
          </pre>
        ) : null}
      </Section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-100">{value}</p>
    </div>
  );
}
