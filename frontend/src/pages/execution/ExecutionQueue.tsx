import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { Section } from "../../components/Section";
import { Spinner } from "../../components/Spinner";

export function ExecutionQueue() {
  const [intents, setIntents] = useState<Array<Record<string, unknown>>>([]);
  const [jobs, setJobs] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [intentRows, jobRows] = await Promise.all([api.executionIntents(), api.executionJobs()]);
      setIntents(intentRows);
      setJobs(jobRows);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (id: string, mode: "execute" | "dry") => {
    if (mode === "execute") await api.executeExecutionIntent(id);
    else await api.dryRunExecutionIntent(id);
    await load();
  };

  if (loading && !intents.length) return <Spinner />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">执行队列</h1>
        <p className="text-xs text-slate-500">冻结意图 → 再校验 → 策略 → 提供方校验 → 执行 → 读后验证 → 审计。</p>
      </div>

      <Section title="执行意图（Intent）">
        <div className="space-y-2">
          {intents.map((intent) => (
            <div key={String(intent.id)} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
              <div className="flex items-center justify-between">
                <Link to={`/execution/intents/${String(intent.id)}`} className="text-sm text-slate-200 hover:text-sky-400">
                  {String(intent.action_type)} · {String(intent.entity_id)}
                </Link>
                <span className="rounded-full px-2 py-0.5 text-[10px] text-slate-400">{String(intent.status)}</span>
              </div>
              <p className="mt-1 text-[10px] text-slate-500">
                风险 {String(intent.risk_level)} · 爆炸半径 {String(intent.blast_radius ?? "—")} · 幂等键 {String(intent.idempotency_key ?? "").slice(0, 12)}
              </p>
              <div className="mt-2 flex gap-2">
                <button onClick={() => void run(String(intent.id), "dry")} className="rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-300">
                  Dry Run
                </button>
                {intent.status === "APPROVED" ? (
                  <button onClick={() => void run(String(intent.id), "execute")} className="rounded border border-emerald-700 px-2 py-1 text-[10px] text-emerald-300">
                    执行
                  </button>
                ) : null}
              </div>
            </div>
          ))}
          {intents.length === 0 ? <p className="py-3 text-sm text-slate-500">暂无执行意图。先在审批队列批准一条推荐。</p> : null}
        </div>
      </Section>

      <Section title="执行任务（Job）">
        <div className="space-y-2">
          {jobs.map((job) => (
            <Link
              key={String(job.id)}
              to={`/execution/jobs/${String(job.id)}`}
              className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2 hover:border-slate-600"
            >
              <div>
                <p className="text-sm text-slate-200">
                  {String(job.action_type)} · {String(job.entity_id)}
                </p>
                <p className="text-[10px] text-slate-500">
                  {String(job.error_code || job.verification_result || "—")} · {String(job.created_at ?? "")}
                </p>
              </div>
              <span className="text-xs text-slate-400">{String(job.status)}</span>
            </Link>
          ))}
          {jobs.length === 0 ? <p className="py-3 text-sm text-slate-500">暂无执行任务。</p> : null}
        </div>
      </Section>
    </div>
  );
}
