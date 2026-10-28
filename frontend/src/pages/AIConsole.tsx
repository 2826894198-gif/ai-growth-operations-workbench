import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";

interface RunRow {
  id: string;
  thread_id: string;
  task_type: string;
  status: string;
  estimated_cost: number;
  created_at?: string | null;
}

export function AIConsole() {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null);
  const [query, setQuery] = useState("");
  const [queryResult, setQueryResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [healthData, runData] = await Promise.all([api.aiHealth(), api.aiRuns()]);
      setHealth(healthData);
      setRuns(runData as unknown as RunRow[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openRun = async (id: string) => {
    setSelectedRun(id);
    setTrace(await api.aiRun(id));
  };

  const runQuery = async () => {
    setQueryResult(null);
    setQueryResult(await api.aiQuery(query));
  };

  if (loading) return <Spinner />;

  const providers = (health.model_providers as Record<string, unknown>) ?? {};

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI 智能控制台"
        subtitle="多 Agent 编排 · 工具权限 · 知识/记忆 · 成本与追踪"
        actions={
          <Link
            to="/rule-console"
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
          >
            ← 规则引擎
          </Link>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="今日运行" value={String(health.runs_today ?? 0)} />
        <Stat label="失败运行" value={String(health.failed_runs ?? 0)} />
        <Stat label="今日成本" value={`$${Number(health.cost_today ?? 0).toFixed(3)}`} />
        <Stat label="注册工具" value={String((health.tool_registry as Record<string, unknown>)?.tools ?? 0)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="模型与基础设施">
          <div className="space-y-2 text-sm">
            <Row label="编排运行时" value={String((health.orchestrator as Record<string, unknown>)?.runtime ?? "langgraph")} />
            <Row label="模式" value={String((health.orchestrator as Record<string, unknown>)?.mode ?? "mock")} />
            <Row label="主推理模型" value={String((providers.primary as Record<string, unknown>)?.model ?? "mock")} />
            <Row label="视频模型" value={String((providers.video as Record<string, unknown>)?.model ?? "mock")} />
            <Row label="知识文档" value={String((health.knowledge as Record<string, unknown>)?.documents ?? 0)} />
            <Row label="业务记忆" value={String((health.memory as Record<string, unknown>)?.memories ?? 0)} />
          </div>
        </Section>

        <Section title="直接查询（0 LLM 门控）">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如：How much did Meta spend yesterday?"
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
          />
          <button
            onClick={() => void runQuery()}
            className="mt-3 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:border-slate-500"
          >
            查询
          </button>
          {queryResult ? (
            <pre className="mt-3 max-h-48 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
              {JSON.stringify(queryResult, null, 2)}
            </pre>
          ) : null}
        </Section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="AI 运行记录">
          {runs.length === 0 ? (
            <p className="py-3 text-sm text-slate-500">暂无运行。执行 make ai-run-daily 或 make seed-ai-demo。</p>
          ) : (
            <div className="max-h-80 overflow-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-xs uppercase text-slate-500">
                    <th className="py-2 pr-2">任务</th>
                    <th className="py-2 pr-2">状态</th>
                    <th className="py-2 pr-2">成本</th>
                    <th className="py-2">时间</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.slice(0, 15).map((run) => (
                    <tr key={run.id} className="cursor-pointer border-b border-slate-800/60 hover:bg-slate-900" onClick={() => void openRun(run.id)}>
                      <td className="py-2 pr-2 text-slate-200">{run.task_type}</td>
                      <td className="py-2 pr-2">
                        <Badge value={run.status} />
                      </td>
                      <td className="py-2 pr-2 text-slate-400">${run.estimated_cost.toFixed(4)}</td>
                      <td className="py-2 text-slate-400">{run.created_at ? new Date(run.created_at).toLocaleString() : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title={selectedRun ? `追踪 ${selectedRun.slice(0, 8)}` : "Agent 追踪"}>
          {trace ? (
            <div className="max-h-80 space-y-2 overflow-auto text-sm">
              {((trace.steps as Array<Record<string, unknown>> | undefined) ?? []).map((step, index) => (
                <div key={index} className="rounded-lg border border-slate-800 bg-slate-950/50 p-2">
                  <div className="flex justify-between">
                    <span className="text-slate-200">{String(step.agent_type)}</span>
                    <span className="text-slate-500">{String(step.model)}</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {String(step.status)} · {String(step.latency_ms)}ms · ${Number(step.cost ?? 0).toFixed(4)}
                  </div>
                </div>
              ))}
              {((trace.tool_calls as Array<Record<string, unknown>> | undefined) ?? []).map((tool, index) => (
                <div key={`t-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/30 p-2 text-xs text-slate-400">
                  {String(tool.agent_type)} → {String(tool.tool_name)} · {String(tool.risk_level)} · {String(tool.duration_ms)}ms
                </div>
              ))}
            </div>
          ) : (
            <p className="py-3 text-sm text-slate-500">点击左侧运行记录查看追踪。</p>
          )}
        </Section>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-100">{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-slate-800/60 py-1.5">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-200">{value}</span>
    </div>
  );
}
