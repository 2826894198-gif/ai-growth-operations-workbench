import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { RecommendationCard } from "../components/recommendation/RecommendationCard";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";
import { Link } from "react-router-dom";

interface Recommendation {
  id: string;
  entity_type: string;
  entity_id: string;
  primary_action: string;
  reason_group: string;
  severity: string;
  confidence: number;
  evidence?: Array<Record<string, unknown>>;
  status: string;
}

export function Recommendations() {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setItems((await api.recommendations()) as unknown as Recommendation[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const transition = async (id: string, status: string) => {
    if (status === "APPROVED") await api.approveRecommendation(id);
    if (status === "REJECTED") await api.rejectRecommendation(id);
    if (status === "ACKNOWLEDGED") await api.acknowledgeRecommendation(id);
    await load();
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">推荐中心</h1>
      <p className="text-xs text-slate-500">批准仅表示业务审批；执行层（PART 06）尚未启用。</p>
      <Section title="开放推荐">
        {items.length === 0 ? (
          <p className="py-4 text-sm text-slate-500">暂无推荐。执行 make rules-load && make rules-evaluate。</p>
        ) : (
          <div className="space-y-3">
            {items.map((rec) => (
              <div key={rec.id} className="space-y-1">
                <RecommendationCard
                  id={rec.id}
                  entityType={rec.entity_type}
                  entityId={rec.entity_id}
                  action={rec.primary_action}
                  reason={rec.reason_group}
                  severity={rec.severity}
                  confidence={rec.confidence}
                  evidence={rec.evidence}
                  onApprove={(id) => void transition(id, "APPROVED")}
                  onReject={(id) => void transition(id, "REJECTED")}
                />
                <Link to={`/recommendations/${rec.id}`} className="ml-1 text-[10px] text-sky-400 hover:underline">
                  打开推荐案例（证据 + 模拟 + 审批 + 执行）
                </Link>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
