import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import { Section } from "../../components/Section";
import { Spinner } from "../../components/Spinner";

export function ApprovalQueue() {
  const [approvals, setApprovals] = useState<Array<Record<string, unknown>>>([]);
  const [recommendations, setRecommendations] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [approvalRows, recRows] = await Promise.all([api.executionApprovals(), api.recommendations()]);
      setApprovals(approvalRows);
      setRecommendations(recRows.filter((rec) => rec.status === "OPEN"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const createApproval = async (recommendationId: string) => {
    await api.createExecutionApproval(recommendationId);
    await load();
  };

  const approve = async (id: string) => {
    await api.approveExecutionApproval(id);
    await load();
  };

  const revoke = async (id: string) => {
    await api.revokeExecutionApproval(id);
    await load();
  };

  if (loading && !approvals.length) return <Spinner />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">审批队列</h1>
        <p className="text-xs text-slate-500">Approval 是冻结动作的一次性绑定：审批后生成执行意图，任何改动都需要新审批。</p>
      </div>

      <Section title="创建审批（从开放推荐）">
        <div className="space-y-2">
          {recommendations.map((rec) => (
            <div key={String(rec.id)} className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2">
              <div>
                <p className="text-sm text-slate-200">
                  {String(rec.primary_action)} · {String(rec.entity_type)} {String(rec.entity_id)}
                </p>
                <p className="text-[10px] text-slate-500">
                  {String(rec.platform || "—")} · 置信度 {Number(rec.confidence).toFixed(2)} · {String(rec.severity)}
                </p>
              </div>
              <button onClick={() => void createApproval(String(rec.id))} className="rounded-lg border border-sky-700 px-3 py-1.5 text-xs text-sky-300">
                生成审批
              </button>
            </div>
          ))}
          {recommendations.length === 0 ? <p className="py-3 text-sm text-slate-500">暂无开放推荐。</p> : null}
        </div>
      </Section>

      <Section title="审批记录">
        <div className="space-y-2">
          {approvals.map((approval) => (
            <div key={String(approval.id)} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-200">
                  {String(approval.action_type)} · {String(approval.entity_id)}
                </p>
                <span className="rounded-full px-2 py-0.5 text-[10px] text-slate-400">{String(approval.status)}</span>
              </div>
              <p className="mt-1 text-[10px] text-slate-500">
                风险 {String(approval.risk_level)} · 过期 {String(approval.expires_at ?? "—")} · 审批人 {String(approval.approved_by)}
              </p>
              <div className="mt-2 flex gap-2">
                {approval.status === "PENDING" ? (
                  <button onClick={() => void approve(String(approval.id))} className="rounded border border-emerald-700 px-2 py-1 text-[10px] text-emerald-300">
                    批准并生成意图
                  </button>
                ) : null}
                {approval.status === "APPROVED" ? (
                  <button onClick={() => void revoke(String(approval.id))} className="rounded border border-rose-700 px-2 py-1 text-[10px] text-rose-300">
                    撤销
                  </button>
                ) : null}
              </div>
            </div>
          ))}
          {approvals.length === 0 ? <p className="py-3 text-sm text-slate-500">暂无审批记录。</p> : null}
        </div>
      </Section>
    </div>
  );
}
