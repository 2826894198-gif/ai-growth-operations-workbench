import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";
import { EntitySummary } from "../components/EntitySummary";
import { EntityTimeline } from "../components/EntityTimeline";
import { MetricCard } from "../components/MetricCard";

type Case = Record<string, unknown>;

export function RecommendationCase() {
  const { id } = useParams();
  const [data, setData] = useState<Case | null>(null);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      setData(await api.recommendationCase(id));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const simulate = async () => {
    if (!id) return;
    setData(await api.simulateCase(id));
  };

  const transition = async (target: string) => {
    if (!id) return;
    setData(await api.transitionCase(id, target));
  };

  const draftIntent = async () => {
    if (!id) return;
    setDraft(await api.draftCaseIntent(id));
  };

  if (loading && !data) return <Spinner />;
  if (!data) return <p className="text-sm text-slate-500">案例不存在</p>;

  const rec = (data.recommendation ?? {}) as Record<string, unknown>;
  const approvals = (data.approvals ?? []) as Array<Record<string, unknown>>;
  const intents = (data.intents ?? []) as Array<Record<string, unknown>>;
  const jobs = (data.jobs ?? []) as Array<Record<string, unknown>>;
  const timeline = (data.timeline ?? []) as Array<{ at?: string; type: string; detail?: string }>;
  const allowed = (data.allowed_transitions ?? []) as string[];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">推荐案例</h1>
          <p className="text-xs text-slate-500">Recommendation Case — 规则证据 + AI 解释 + 模拟 + 审批 + 执行，一条可追踪决策链。</p>
        </div>
        <div className="flex gap-2">
          {allowed.includes("SIMULATED") ? (
            <button onClick={() => void simulate()} className="rounded-lg border border-sky-700 px-3 py-1.5 text-xs text-sky-300">
              模拟影响
            </button>
          ) : null}
          {allowed.includes("PENDING_APPROVAL") ? (
            <button onClick={() => void transition("PENDING_APPROVAL")} className="rounded-lg border border-amber-700 px-3 py-1.5 text-xs text-amber-300">
              提交审批
            </button>
          ) : null}
          {allowed.includes("APPROVED") ? (
            <button onClick={() => void transition("APPROVED")} className="rounded-lg border border-emerald-700 px-3 py-1.5 text-xs text-emerald-300">
              批准
            </button>
          ) : null}
          {allowed.includes("REJECTED") ? (
            <button onClick={() => void transition("REJECTED")} className="rounded-lg border border-rose-700 px-3 py-1.5 text-xs text-rose-300">
              拒绝
            </button>
          ) : null}
          <button onClick={() => void draftIntent()} className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300">
            起草执行意图
          </button>
        </div>
      </div>

      <EntitySummary
        title={`${String(rec.primary_action ?? "")} · ${String(rec.entity_type ?? "")} ${String(rec.entity_id ?? "")}`}
        subtitle={`${String(rec.reason_group ?? "")} · 严重度 ${String(rec.severity ?? "")} · 置信度 ${Number(rec.confidence ?? 0).toFixed(2)} · 案例状态 ${String(rec.case_status ?? "")}`}
        avatar={String(rec.platform ?? "?").slice(0, 1)}
        meta={[
          { label: "变更幅度", value: rec.suggested_change_pct != null ? `${Number(rec.suggested_change_pct)}%` : "—" },
          { label: "canonical entity", value: String(rec.canonical_entity_id ?? "未注册") },
        ]}
      />

      {draft ? (
        <Section title="执行意图草稿（未执行）">
          <pre className="max-h-64 overflow-auto rounded-lg bg-slate-950 p-3 text-[10px] text-slate-400">{JSON.stringify(draft, null, 2)}</pre>
        </Section>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Section title="规则证据">
            {Array.isArray(rec.evidence) && (rec.evidence as unknown[]).length ? (
              <table className="w-full text-left text-xs">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-2">指标</th>
                    <th>当前</th>
                    <th>基线</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  {(rec.evidence as Array<Record<string, unknown>>).map((item, index) => (
                    <tr key={index} className="border-t border-slate-800 text-slate-300">
                      <td className="py-2">{String(item.metric ?? "")}</td>
                      <td>{String(item.current ?? "")}</td>
                      <td>{String(item.baseline ?? "")}</td>
                      <td>{String(item.note ?? "")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="py-2 text-sm text-slate-500">无量化证据。</p>
            )}
          </Section>

          <Section title="模拟影响">
            {rec.simulated_impact ? (
              <div className="grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
                {(Object.entries(rec.simulated_impact as Record<string, unknown>) ?? []).slice(0, 6).map(([key, value]) => (
                  <div key={key}>
                    <p className="text-slate-500">{key}</p>
                    <p className="text-slate-200">{String(value ?? "")}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-2 text-sm text-slate-500">尚未模拟。点击“模拟影响”生成确定性估算（不含拍卖/受众效应）。</p>
            )}
          </Section>

          <Section title="审批 / 意图 / 任务">
            <div className="space-y-2 text-xs">
              {approvals.map((approval) => (
                <div key={String(approval.id)} className="rounded border border-slate-800 bg-slate-900/40 px-3 py-2">
                  审批 {String(approval.status)} · 风险 {String(approval.risk_level)} · {String(approval.approved_by)}
                </div>
              ))}
              {intents.map((intent) => (
                <div key={String(intent.id)} className="rounded border border-slate-800 bg-slate-900/40 px-3 py-2">
                  意图 {String(intent.status)} · {String(intent.action_type)} · 绑定 {String(intent.action_package_hash ?? "").slice(0, 12)}
                </div>
              ))}
              {jobs.map((job) => (
                <div key={String(job.id)} className="rounded border border-slate-800 bg-slate-900/40 px-3 py-2">
                  任务 {String(job.status)} · 验证 {String(job.verification_result ?? "—")} · {String(job.error_code ?? "")}
                </div>
              ))}
              {!approvals.length && !intents.length && !jobs.length ? <p className="py-2 text-sm text-slate-500">尚无审批/执行记录。</p> : null}
            </div>
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="决策时间线">
            <EntityTimeline events={timeline} />
          </Section>
          <Section title="AI 解释">
            <p className="text-xs leading-relaxed text-slate-300">{String(rec.ai_explanation ?? "（待 AI 生成解释；当前规则证据可直接阅读）")}</p>
          </Section>
          <Section title="决策理由">
            <p className="text-xs leading-relaxed text-slate-300">{String(rec.decision_reason ?? "未记录")}</p>
          </Section>
        </div>
      </div>
      <MetricCard label="案例状态" value={String(rec.case_status ?? "DRAFT")} hint="可执行转换见上方按钮" />
    </div>
  );
}
