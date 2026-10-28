import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Section } from "../../components/Section";
import { Spinner } from "../../components/Spinner";

export function ExecutionDetail() {
  const { intentId, jobId } = useParams();
  const [intent, setIntent] = useState<Record<string, unknown> | null>(null);
  const [job, setJob] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (intentId) setIntent(await api.executionIntent(intentId));
      if (jobId) setJob(await api.executionJob(jobId));
    } finally {
      setLoading(false);
    }
  }, [intentId, jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !intent && !job) return <Spinner />;

  const events = ((intent?.events ?? job?.events ?? []) as Array<Record<string, unknown>>).slice().reverse();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">执行详情</h1>
      {intent ? (
        <Section title={`意图 ${String(intent.id)}`}>
          <div className="grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
            <div><p className="text-slate-500">动作</p><p className="text-slate-200">{String(intent.action_type)}</p></div>
            <div><p className="text-slate-500">实体</p><p className="text-slate-200">{String(intent.entity_id)}</p></div>
            <div><p className="text-slate-500">风险</p><p className="text-slate-200">{String(intent.risk_level)}</p></div>
            <div><p className="text-slate-500">状态</p><p className="text-slate-200">{String(intent.status)}</p></div>
          </div>
          <pre className="mt-3 max-h-48 overflow-auto rounded-lg bg-slate-950 p-3 text-[10px] text-slate-400">
            {JSON.stringify(intent.requested_change, null, 2)}
          </pre>
        </Section>
      ) : null}
      {job ? (
        <Section title={`任务 ${String(job.id)}`}>
          <div className="grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
            <div><p className="text-slate-500">状态</p><p className="text-slate-200">{String(job.status)}</p></div>
            <div><p className="text-slate-500">再校验</p><p className="text-slate-200">{String(job.revalidation_result ?? "—")}</p></div>
            <div><p className="text-slate-500">验证</p><p className="text-slate-200">{String(job.verification_result ?? "—")}</p></div>
            <div><p className="text-slate-500">错误</p><p className="text-rose-300">{String(job.error_code ?? "—")}</p></div>
          </div>
          {job.error_message ? <p className="mt-2 text-xs text-rose-300">{String(job.error_message)}</p> : null}
          {Array.isArray(job.compensations) && (job.compensations as unknown[]).length ? (
            <div className="mt-3">
              <p className="mb-1 text-xs text-slate-400">补偿记录</p>
              {(job.compensations as Array<Record<string, unknown>>).map((compensation) => (
                <div key={String(compensation.id)} className="rounded border border-slate-800 bg-slate-900/40 px-3 py-2 text-xs">
                  <span className="text-slate-200">{String(compensation.compensation_type)}</span>
                  <span className="ml-2 text-slate-500">{String(compensation.status)}</span>
                </div>
              ))}
            </div>
          ) : null}
        </Section>
      ) : null}
      <Section title="时间线">
        <div className="space-y-1">
          {events.map((event, index) => (
            <div key={index} className="flex justify-between rounded border border-slate-800 bg-slate-900/30 px-3 py-1.5 text-xs">
              <span className="text-slate-300">{String(event.event_type)}</span>
              <span className="text-slate-500">{String(event.created_at ?? "")}</span>
            </div>
          ))}
          {events.length === 0 ? <p className="py-2 text-sm text-slate-500">暂无事件。</p> : null}
        </div>
      </Section>
    </div>
  );
}
