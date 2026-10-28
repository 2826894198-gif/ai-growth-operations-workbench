import { Link } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle,
  Database,
  LockKey,
  Plugs,
  WarningCircle,
} from "@phosphor-icons/react";
import {
  AvailabilityBadge,
  CapabilityTable,
  DataLayerBadge,
  DemoBadge,
  DemoNotice,
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

export function InstagramDataHealth() {
  const { overview, content, loading, error, reload } = useInstagramData(28);
  const model = instagramReadModel(overview, content);
  const liveReady = false;
  const availableCount = model.capabilities.filter((item) => asText(item.reason) === "available").length;
  const permissionCount = model.capabilities.filter((item) => asText(item.reason) === "permission_denied").length;
  const unsupportedCount = model.capabilities.filter((item) => asText(item.reason) === "unsupported").length;

  if (loading && !overview) return <div className="instagram-page"><LoadingState /></div>;
  if (error && !overview) return <div className="instagram-page"><PageError message={error} /></div>;

  return (
    <div className="instagram-page">
      <header className="instagram-page-header">
        <div className="instagram-page-title">
          <div className="instagram-page-title-mark"><Plugs size={24} weight="duotone" /></div>
          <div><div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}><h1>Connection / Data Health</h1><DemoBadge compact /></div><p>Connection mode, API capability coverage, freshness and server-side token boundaries.</p></div>
        </div>
        <div className="instagram-page-actions"><button type="button" className="instagram-outline-button" onClick={reload}><Database size={14} /> Re-check read model</button><Link to="/settings/connections" className="instagram-primary-button">Open integrations <ArrowRight size={14} /></Link></div>
      </header>
      <DemoNotice fixtureVersion={asText(model.source.fixture_version)}>Live sync is deliberately disabled in this phase. The readiness blocks below tell you what is still needed without collecting credentials in the frontend.</DemoNotice>

      <div className="ig-inline-grid">
        <section className="ig-panel">
          <InstagramSectionHeader eyebrow="Connection state" title="Instagram Login · not connected" description="V1 supports Professional Business / Creator accounts only." action={<span className="ig-status-pill is-calibrating"><WarningCircle size={12} weight="bold" /> ACTION REQUIRED</span>} />
          <div className="ig-source-summary"><Plugs size={18} /><div><strong>Demo fixture is active</strong><span>Last fixture sync {formatDateTime(model.account.last_sync)} · no OAuth callback or token persistence is running.</span></div></div>
          <div className="ig-raw-stat-grid" style={{ marginTop: 12 }}>
            <div className="ig-raw-stat"><span>Live sync</span><strong>OFF</strong><small>backend connector pending</small></div>
            <div className="ig-raw-stat"><span>Token location</span><strong>SERVER</strong><small>never in browser</small></div>
            <div className="ig-raw-stat"><span>API version</span><strong>v26.0</strong><small>META_GRAPH_API_VERSION</small></div>
          </div>
        </section>
        <section className="ig-panel">
          <InstagramSectionHeader eyebrow="Capability coverage" title="Permission-aware metrics" description="Counts describe fields in the fixture, not the quality of the account." action={<DataLayerBadge layer="RAW" />} />
          <div className="ig-raw-stat-grid">
            <div className="ig-raw-stat"><span>Available</span><strong>{availableCount}</strong><small>provider fields present</small></div>
            <div className="ig-raw-stat"><span>Permission</span><strong>{permissionCount}</strong><small>need approved scope</small></div>
            <div className="ig-raw-stat"><span>Unsupported</span><strong>{unsupportedCount}</strong><small>keep null, do not zero</small></div>
          </div>
          <div className="ig-panel-note"><LockKey size={14} /><span>Required scopes are configured server-side; no secret is rendered here.</span></div>
        </section>
      </div>

      <section className="ig-panel">
        <InstagramSectionHeader eyebrow="Metric capability matrix" title="What the API can currently support" description="Every row carries a reason, provider field and permission state." action={<span className="ig-layer-badge is-raw">CAPABILITIES</span>} />
        <CapabilityTable capabilities={model.capabilities} />
      </section>

      <section className="ig-panel">
        <InstagramSectionHeader eyebrow="Live connection checklist" title="Prepare once, then connect safely" description="This is an operational checklist, not a browser token form." action={<AvailabilityBadge reason={liveReady ? "available" : "permission_denied"} />} />
        <div className="ig-connection-steps">
          <div className="ig-connection-step"><span className="ig-connection-step-number">01</span><h3>Confirm Professional account</h3><p>Use Business or Creator. A personal account is not a supported V1 source.</p></div>
          <div className="ig-connection-step"><span className="ig-connection-step-number">02</span><h3>Configure Meta app</h3><p>Set client ID, secret reference, redirect URI, scopes and META_GRAPH_API_VERSION on the server.</p></div>
          <div className="ig-connection-step"><span className="ig-connection-step-number">03</span><h3>Run preflight and OAuth</h3><p>Validate callback allowlist, token exchange, account discovery and capability checks before enabling sync.</p></div>
        </div>
        <div className="ig-panel-note"><CheckCircle size={14} color="#6ee7b7" /><span>Runbook: backend/app/core/config.py + docs/runbooks/instagram-live-api-setup.md</span><Link to="/settings/connections" className="ig-text-link">Go to integrations <ArrowRight size={14} /></Link></div>
      </section>
    </div>
  );
}
