import { Link } from "react-router-dom";
import {
  ArrowRight,
  Clock,
  Info,
  LockKey,
  UsersThree,
} from "@phosphor-icons/react";
import {
  AvailabilityBadge,
  DataLayerBadge,
  DemoBadge,
  DemoNotice,
  EmptyMetric,
  InstagramSectionHeader,
  LoadingState,
  PageError,
} from "./instagram/InstagramPrimitives";
import {
  asText,
  formatDateTime,
  instagramReadModel,
  useInstagramData,
} from "./instagram/instagramData";

export function InstagramAudience() {
  const { overview, content, loading, error } = useInstagramData(28);
  const model = instagramReadModel(overview, content);
  const ageCapability = model.capabilities.find((item) => asText(item.metric_key) === "audience_age");
  const ageReason = asText(ageCapability?.reason, "permission_denied");
  const lastSync = formatDateTime(model.account.last_sync);

  if (loading && !overview) return <div className="instagram-page"><LoadingState /></div>;
  if (error && !overview) return <div className="instagram-page"><PageError message={error} /></div>;

  return (
    <div className="instagram-page">
      <header className="instagram-page-header">
        <div className="instagram-page-title">
          <div className="instagram-page-title-mark"><UsersThree size={24} weight="duotone" /></div>
          <div><div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}><h1>Audience</h1><DemoBadge compact /></div><p>Real audience fields first. Target Fit is separate from a speculative audience quality score.</p></div>
        </div>
        <div className="instagram-page-actions"><Link to="/instagram" className="instagram-outline-button">Back to overview <ArrowRight size={13} /></Link></div>
      </header>
      <DemoNotice fixtureVersion={asText(model.source.fixture_version)}>The fixture does not contain audience segments, interests or locations. No audience persona is invented from the account name.</DemoNotice>

      <div className="ig-inline-grid">
        <section className="ig-panel">
          <InstagramSectionHeader eyebrow="Audience Target Fit" title="Audience evidence" description="This panel only uses fields returned by the provider read model." action={<DataLayerBadge layer="RAW" />} />
          <EmptyMetric title="Audience age and gender unavailable" reason={`Capability reason: ${ageReason}. Request the required Professional Insights permission before using this dimension.`} action={<AvailabilityBadge reason={ageReason} />} />
          <div className="ig-raw-stat-grid" style={{ marginTop: 12 }}>
            <div className="ig-raw-stat"><span>Age breakdown</span><strong>—</strong><small>not returned</small></div>
            <div className="ig-raw-stat"><span>Gender breakdown</span><strong>—</strong><small>not returned</small></div>
            <div className="ig-raw-stat"><span>Top locations</span><strong>—</strong><small>not returned</small></div>
          </div>
        </section>
        <section className="ig-panel">
          <InstagramSectionHeader eyebrow="Workspace persona" title="Current / previous / delta" description="Persona changes require enough history and explicit evidence." action={<DataLayerBadge layer="AI INFERENCE" />} />
          <div className="ig-detail-list">
            <details className="ig-detail-item" open><summary><span>Current persona</span><span className="ig-score-pill is-calibrating">NOT BUILT</span></summary><p>No current persona is generated. Account type is {asText(model.account.account_type, "CREATOR")}; that is not a demographic segment.</p></details>
            <details className="ig-detail-item"><summary><span>Previous persona</span><span className="ig-layer-badge is-muted">—</span></summary><p>The Demo fixture has no prior audience persona record.</p></details>
            <details className="ig-detail-item"><summary><span>Delta</span><span className="ig-layer-badge is-muted">—</span></summary><p>Audience drift cannot be evaluated without current and previous audience dimensions.</p></details>
          </div>
        </section>
      </div>

      <section className="ig-panel">
        <InstagramSectionHeader eyebrow="Best posting time" title="Online followers / posting history" description="Only calculate a time slot when there are at least 5 posts in the day × hour bucket." action={<span className="ig-status-pill is-calibrating"><Clock size={12} weight="bold" /> INSUFFICIENT DATA</span>} />
        <div className="ig-empty-metric">
          <div className="ig-empty-metric-icon"><Clock size={18} weight="duotone" /></div>
          <div className="ig-empty-metric-copy"><strong>Best posting time is not available in this fixture</strong><span>There is no online_followers series and only three media records, so the dashboard does not publish a fabricated “best time”.</span><div className="ig-empty-metric-action"><Link to="/instagram/data-health" className="ig-text-link">See required fields <ArrowRight size={14} /></Link></div></div>
        </div>
      </section>

      <section className="ig-panel">
        <InstagramSectionHeader eyebrow="Audience data contract" title="What will appear after Live sync" description={`Last fixture sync ${lastSync}. These are capability-aware slots, not generated values.`} action={<Info size={16} color="#8d99aa" />} />
        <div className="ig-connection-steps">
          <div className="ig-connection-step"><span className="ig-connection-step-number">01</span><h3>Provider audience fields</h3><p>Age, gender, country/city and online followers, only when the API returns them.</p></div>
          <div className="ig-connection-step"><span className="ig-connection-step-number">02</span><h3>Target Fit</h3><p>Compare current evidence with workspace persona and log missing fields separately.</p></div>
          <div className="ig-connection-step"><span className="ig-connection-step-number">03</span><h3>Drift rule</h3><p>Only trigger AUDIENCE_DRIFT after current and previous dimensions are both valid.</p></div>
        </div>
        <div className="ig-panel-note"><LockKey size={14} /><span>Instagram Login requires the permission set configured in the server-side connection runbook.</span><Link to="/instagram/data-health" className="ig-text-link">Open readiness <ArrowRight size={14} /></Link></div>
      </section>
    </div>
  );
}
