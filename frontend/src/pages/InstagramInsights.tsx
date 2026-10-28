import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Brain,
  CheckCircle,
  Info,
  Sparkle,
  WarningCircle,
} from "@phosphor-icons/react";
import {
  DataLayerBadge,
  DemoBadge,
  DemoNotice,
  EmptyMetric,
  InstagramSectionHeader,
  LoadingState,
  PageError,
  contentRuleEvaluations,
} from "./instagram/InstagramPrimitives";
import {
  asRecord,
  asText,
  instagramReadModel,
  useInstagramData,
} from "./instagram/instagramData";

const RULE_CATALOG = [
  ["WINNING_CONTENT", "Is this content strong against its same-type baseline?"],
  ["BREAKOUT_CANDIDATE", "Is reach materially above baseline with enough quality evidence?"],
  ["ENGAGEMENT_ANOMALY", "Is engagement unusually high or low versus baseline?"],
  ["AUDIENCE_DRIFT", "Has target fit materially changed?"],
  ["PROFILE_LINK_LEAKAGE", "Are profile views failing to become link taps?"],
  ["HIGH_REACH_LOW_INTENT", "Is distribution strong while intent is weak?"],
  ["STRONG_INTENT_LOW_DISTRIBUTION", "Is intent strong while distribution is weak?"],
  ["CONTENT_DECAY", "Has this content decayed below its baseline?"],
] as const;

function RuleCatalog({ rows }: { rows: Array<Record<string, unknown>> }) {
  const rules = useMemo(() => RULE_CATALOG.map(([code, question]) => {
    const evaluation = rows
      .flatMap((candidate) => contentRuleEvaluations(candidate))
      .find((item) => asText(item.rule_code) === code);
    const evidence = asRecord(evaluation?.evidence);
    const observations = asRecord(evidence.observations);
    return { code, question, status: asText(evaluation?.status, "INSUFFICIENT_DATA"), missing: Array.isArray(evaluation?.missing_fields) ? evaluation.missing_fields.map(String) : [], observations };
  }), [rows]);

  return (
    <div className="ig-rule-table">
      <div className="ig-rule-row is-head"><span>Rule</span><span>State</span><span>Confidence</span><span>Evidence requirement</span></div>
      {rules.map((rule) => (
        <div className="ig-rule-row" key={rule.code}>
          <span className="ig-rule-code">{rule.code}</span>
          <span className="ig-rule-state">{rule.status.replace(/_/g, " ")}</span>
          <span>{rule.status === "INSUFFICIENT_DATA" ? "—" : "available"}</span>
          <span>{rule.missing.length ? `Missing ${rule.missing.join(", ")}` : rule.question}</span>
        </div>
      ))}
    </div>
  );
}

export function InstagramInsights() {
  const { overview, content, loading, error } = useInstagramData(28);
  const model = instagramReadModel(overview, content);
  const firstRow = model.rows[0];

  if (loading && !overview) return <div className="instagram-page"><LoadingState /></div>;
  if (error && !overview) return <div className="instagram-page"><PageError message={error} /></div>;

  return (
    <div className="instagram-page">
      <header className="instagram-page-header">
        <div className="instagram-page-title">
          <div className="instagram-page-title-mark"><Sparkle size={24} weight="fill" /></div>
          <div><div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}><h1>AI Insights</h1><DemoBadge compact /></div><p>Rules first, AI explanation second. No unsupported claim is promoted to an insight.</p></div>
        </div>
        <div className="instagram-page-actions"><Link to="/instagram" className="instagram-outline-button">Back to overview <ArrowRight size={13} /></Link></div>
      </header>
      <DemoNotice fixtureVersion={asText(model.source.fixture_version)}>The AI layer is not generated from a missing evidence pack. This page exposes the rule state and the exact reasons for withholding inference.</DemoNotice>

      <div className="ig-insight-grid">
        <section className="ig-panel ig-insight-panel">
          <InstagramSectionHeader eyebrow="AI inference state" title="No AI insight is publishable yet" description="AI must explain a deterministic evidence pack; it cannot fill missing baselines or audience fields." action={<DataLayerBadge layer="AI_INFERENCE" />} />
          <div className="ig-insight-body">
            <div className="ig-insight-lead">
              <div className="ig-insight-lead-top"><Brain size={15} weight="duotone" /> Inference gate</div>
              <h3>Evidence coverage is below the V1 confidence threshold.</h3>
              <p>When Live data is connected, each insight will include source refs, calculation versions, confidence, model and prompt metadata. The current fixture intentionally stops before that layer.</p>
              <div className="ig-evidence-list">
                <div className="ig-evidence-item"><span>Source mode</span><span>DEMO</span></div>
                <div className="ig-evidence-item"><span>Evidence pack</span><span>Not built</span></div>
                <div className="ig-evidence-item"><span>Confidence</span><span>—</span></div>
                <div className="ig-evidence-item"><span>Max recommendations</span><span>3</span></div>
              </div>
            </div>
            <div className="ig-insight-evidence">
              <div className="ig-evidence-block"><label>Model</label><strong>Not configured</strong><small>AI provider remains a separate dependency</small></div>
              <div className="ig-evidence-block"><label>Language</label><strong>Tentative</strong><small>Low confidence must not sound certain</small></div>
              <Link to="/instagram/data-health" className="instagram-primary-button">Open data health <ArrowRight size={14} /></Link>
            </div>
          </div>
        </section>
        <section className="ig-panel">
          <InstagramSectionHeader eyebrow="Recommendation guardrail" title="What can be recommended now?" description="Only operational data-collection actions are safe while the baseline is incomplete." action={<WarningCircle size={17} color="#f6c96d" />} />
          <div className="ig-detail-list">
            <details className="ig-detail-item" open><summary><span>Collect account history</span><CheckCircle size={14} color="#f6c96d" /></summary><p>Account health requires at least 21 valid days before a precise score is shown.</p></details>
            <details className="ig-detail-item"><summary><span>Collect same-type content</span><CheckCircle size={14} color="#f6c96d" /></summary><p>Content score requires at least 10 comparable media records and minimum reach checks.</p></details>
            <details className="ig-detail-item"><summary><span>Connect Professional Insights</span><CheckCircle size={14} color="#f6c96d" /></summary><p>Use the server-side OAuth connection flow; do not paste a Meta token into the browser.</p></details>
          </div>
        </section>
      </div>

      <section className="ig-panel">
        <InstagramSectionHeader eyebrow="Rule engine" title="Eight V1 rules, one traceable state" description="Rule status is deterministic and missing fields remain explicit." action={<span className="ig-layer-badge is-derived">rule-engine-v1.0</span>} />
        <RuleCatalog rows={model.rows} />
      </section>

      <section className="ig-panel">
        <InstagramSectionHeader eyebrow="Evidence drawer" title="Latest content evidence" description="Inspect the exact missing fields from the first synced media record." action={<Info size={16} color="#8d99aa" />} />
        {firstRow ? (
          <div className="ig-detail-list">
            {contentRuleEvaluations(firstRow).slice(0, 4).map((evaluation) => {
              const code = asText(evaluation.rule_code, "RULE");
              const status = asText(evaluation.status, "INSUFFICIENT_DATA");
              const evidence = asRecord(evaluation.evidence);
              const refs = Array.isArray(evidence.input_refs) ? evidence.input_refs.map(String) : [];
              return <details className="ig-detail-item" key={code}><summary><span>{code}</span><span className="ig-rule-state">{status.replace(/_/g, " ")}</span></summary><p>Missing fields: {Array.isArray(evaluation.missing_fields) && evaluation.missing_fields.length ? evaluation.missing_fields.map(String).join(", ") : "none"}. Evidence refs: {refs.length ? refs.join(", ") : "none"}.</p></details>;
            })}
          </div>
        ) : <EmptyMetric title="No evidence pack" reason="No content rows are available in this window." />}
      </section>
    </div>
  );
}
