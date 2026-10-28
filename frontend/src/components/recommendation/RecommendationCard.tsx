import { useState } from "react";
import { EvidenceDrawer } from "../evidence/EvidenceDrawer";
import { SeverityBadge } from "../status/SeverityBadge";

interface RecommendationCardProps {
  id: string;
  entityType: string;
  entityId: string;
  action: string;
  reason: string;
  severity: string;
  confidence: number;
  evidence?: Array<Record<string, unknown>>;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
}

export function RecommendationCard({ id, entityType, entityId, action, reason, severity, confidence, evidence = [], onApprove, onReject }: RecommendationCardProps) {
  const [showEvidence, setShowEvidence] = useState(false);
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <SeverityBadge value={severity} />
            <span className="text-sm font-medium text-slate-200">{reason}</span>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            {entityType} · {entityId} · {action}
          </p>
          <p className="mt-1 text-xs text-slate-500">置信度 {(confidence * 100).toFixed(0)}%</p>
        </div>
        <div className="flex shrink-0 gap-2">
          {onApprove ? (
            <button onClick={() => onApprove(id)} className="rounded-md border border-emerald-500/40 px-2 py-1 text-xs text-emerald-300">
              批准
            </button>
          ) : null}
          {onReject ? (
            <button onClick={() => onReject(id)} className="rounded-md border border-rose-500/40 px-2 py-1 text-xs text-rose-300">
              拒绝
            </button>
          ) : null}
          <button onClick={() => setShowEvidence(true)} className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300">
            Why?
          </button>
        </div>
      </div>
      <EvidenceDrawer open={showEvidence} onClose={() => setShowEvidence(false)}>
        <div className="space-y-2 text-sm">
          {evidence.length === 0 ? (
            <p className="text-slate-500">无量化证据。</p>
          ) : (
            evidence.map((item, index) => (
              <div key={index} className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                <p className="text-slate-300">
                  {String(item.metric ?? "metric")}: <span className="tabular-nums">{String(item.current ?? "—")}</span>
                </p>
                {item.baseline != null ? <p className="text-xs text-slate-500">基线 {String(item.baseline)}</p> : null}
                {item.source_ref ? <p className="text-xs text-slate-500">{String(item.source_ref)}</p> : null}
              </div>
            ))
          )}
        </div>
      </EvidenceDrawer>
    </div>
  );
}
