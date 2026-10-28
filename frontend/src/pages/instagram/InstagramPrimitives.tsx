import { Link } from "react-router-dom";
import {
  ArrowRight,
  ChartLineUp,
  Clock,
  Info,
  LockKey,
  Play,
  WarningCircle,
} from "@phosphor-icons/react";
import {
  DEMO_THUMBNAIL,
  JsonRecord,
  asNumber,
  asRecord,
  asText,
  availabilityLabel,
  availabilityTone,
  formatDate,
  formatNumber,
  formatPercent,
  mediaLabel,
  metricCell,
  metricValue,
} from "./instagramData";

export function InstagramSectionHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="ig-section-header">
      <div className="ig-section-heading">
        {eyebrow ? <p className="ig-eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {description ? <p className="ig-section-description">{description}</p> : null}
      </div>
      {action ? <div className="ig-section-action">{action}</div> : null}
    </div>
  );
}

export function DemoBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`ig-badge ig-badge-demo ${compact ? "is-compact" : ""}`}>
      <span className="ig-status-dot" aria-hidden="true" />
      DEMO · NOT LIVE
    </span>
  );
}

export function DataLayerBadge({ layer = "RAW" }: { layer?: string }) {
  const tone = layer === "DERIVED" ? "is-derived" : layer === "AI_INFERENCE" ? "is-ai" : "is-raw";
  return <span className={`ig-layer-badge ${tone}`}>{layer.replace(/_/g, " ")}</span>;
}

export function AvailabilityBadge({ reason }: { reason?: string }) {
  const normalized = reason || "unavailable";
  return (
    <span className={`ig-availability ${availabilityTone(normalized)}`}>
      {normalized === "permission_denied" ? <LockKey size={12} weight="bold" /> : null}
      {availabilityLabel(normalized)}
    </span>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  source,
  accent = "violet",
  icon,
  trend,
  onClick,
}: {
  label: string;
  value: string;
  detail: string;
  source?: string;
  accent?: "violet" | "blue" | "green" | "orange" | "pink" | "slate";
  icon?: React.ReactNode;
  trend?: string;
  onClick?: () => void;
}) {
  const content = (
    <>
      <div className="ig-metric-card-top">
        <span>{label}</span>
        <span className={`ig-metric-icon is-${accent}`}>{icon}</span>
      </div>
      <div className="ig-metric-value">{value}</div>
      <div className="ig-metric-meta">
        {trend ? <span className="ig-metric-trend">{trend}</span> : null}
        <span>{detail}</span>
      </div>
      {source ? <div className="ig-metric-source">{source}</div> : null}
    </>
  );
  return onClick ? (
    <button type="button" className="ig-metric-card ig-metric-card-button" onClick={onClick}>
      {content}
    </button>
  ) : (
    <article className="ig-metric-card">{content}</article>
  );
}

export function MetricTooltip({ children }: { children: React.ReactNode }) {
  return (
    <span className="ig-tooltip-trigger" tabIndex={0}>
      <Info size={13} weight="bold" />
      <span className="ig-tooltip">{children}</span>
    </span>
  );
}

export function EmptyMetric({
  title,
  reason,
  action,
}: {
  title: string;
  reason: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="ig-empty-metric">
      <div className="ig-empty-metric-icon"><WarningCircle size={18} weight="duotone" /></div>
      <div className="ig-empty-metric-copy">
        <strong>{title}</strong>
        <span>{reason}</span>
        {action ? <div className="ig-empty-metric-action">{action}</div> : null}
      </div>
    </div>
  );
}

export function ContentCard({
  row,
  index,
  compact = false,
}: {
  row: JsonRecord;
  index: number;
  compact?: boolean;
}) {
  const media = asRecord(row.media);
  const raw = asRecord(row.raw);
  const rawMetrics = asRecord(raw.metrics);
  const derived = asRecord(row.derived);
  const mediaType = asText(media.media_type, "MEDIA");
  const title = asText(media.caption, "Untitled media");
  const score = asNumber(row.content_score);
  const watchRatio = metricValue(derived, "watch_ratio");
  const sourceStatus = asText(raw.source_layer, "RAW");
  const thumbnail = asText(media.thumbnail_url) || DEMO_THUMBNAIL;
  const contentHref = `/instagram/content?media=${encodeURIComponent(asText(media.external_media_id, String(index)))}`;

  return (
    <article className={`ig-content-card ${compact ? "is-compact" : ""}`}>
      <Link to={contentHref} className="ig-content-thumbnail" aria-label={`Open ${title}`}>
        <img src={thumbnail} alt="Demo cassette player creative" />
        <span className="ig-content-thumbnail-overlay" />
        {mediaType === "REELS" ? <span className="ig-play-button"><Play size={15} weight="fill" /></span> : null}
        <span className="ig-content-rank">{index + 1}</span>
        <span className="ig-content-asset-label">DEMO ASSET</span>
      </Link>
      <div className="ig-content-card-body">
        <div className="ig-content-card-topline">
          <span className="ig-content-type">{mediaLabel(mediaType)}</span>
          <span className="ig-content-date">{formatDate(media.published_at, true)}</span>
        </div>
        <Link to={contentHref} className="ig-content-title">{title}</Link>
        <div className="ig-content-stats">
          <div><span>Reach</span><strong>{formatNumber(metricValue(rawMetrics, "reach"), { notation: "compact" })}</strong></div>
          <div><span>ER</span><strong>{formatPercent(metricValue(derived, "engagement_rate_by_reach"))}</strong></div>
          <div><span>{mediaType === "REELS" ? "Watch" : "Saves"}</span><strong>{mediaType === "REELS" ? formatPercent(watchRatio) : formatNumber(metricValue(rawMetrics, "saved"), { notation: "compact" })}</strong></div>
        </div>
        <div className="ig-content-card-footer">
          <span className={`ig-score-pill ${score === null ? "is-calibrating" : "is-available"}`}>
            {score === null ? "CALIBRATING" : `${Math.round(score)}/100`}
          </span>
          <DataLayerBadge layer={sourceStatus} />
        </div>
      </div>
    </article>
  );
}

export function HealthPanel({ health }: { health: JsonRecord }) {
  const score = asNumber(health.score);
  const confidence = asNumber(health.confidence);
  const missing = Array.isArray(health.missing_dimensions) ? health.missing_dimensions.map(String) : [];
  const dimensions = [
    ["Content quality", "content_quality"],
    ["Growth", "growth"],
    ["Engagement", "engagement"],
    ["Audience fit", "audience_fit"],
    ["Conversion intent", "conversion_intent"],
  ] as const;
  const dimensionValues = asRecord(health.dimensions);

  return (
    <section className="ig-panel ig-health-panel">
      <InstagramSectionHeader
        eyebrow="Account health"
        title="Account Health Score"
        description="Internal score only. It does not represent an official Meta rating."
        action={<span className="ig-status-pill is-calibrating"><Clock size={12} weight="bold" /> CALIBRATING</span>}
      />
      <div className="ig-health-summary">
        <div className="ig-score-ring" aria-label={score === null ? "Health score calibrating" : `Health score ${Math.round(score)}`}>
          <div><strong>{score === null ? "—" : Math.round(score)}</strong><span>/ 100</span></div>
        </div>
        <div className="ig-health-copy">
          <strong>History is still below V1 minimums</strong>
          <p>Collect at least 21 valid account days and 10 same-type content items before publishing a precise health score.</p>
          <div className="ig-health-factors">
            <span>Confidence {confidence === null ? "—" : formatPercent(confidence)}</span>
            <span>Sample {asText(health.sample_size, "insufficient")}</span>
          </div>
        </div>
      </div>
      <div className="ig-dimension-list">
        {dimensions.map(([label, key]) => {
          const value = asNumber(dimensionValues[key]);
          return (
            <div className="ig-dimension-row" key={key}>
              <div className="ig-dimension-label"><span>{label}</span><span>{value === null ? "—" : Math.round(value)}</span></div>
              <div className="ig-dimension-track"><span style={{ width: value === null ? "0%" : `${Math.max(0, Math.min(100, value))}%` }} /></div>
            </div>
          );
        })}
      </div>
      <div className="ig-panel-note">
        <Info size={14} />
        <span>{missing.length ? `Missing dimensions: ${missing.join(", ")}` : "Missing fields are reweighted and logged."}</span>
        <span className="ig-version">{asText(health.calculation_version, "health-v1.0")}</span>
      </div>
    </section>
  );
}

export function CapabilityTable({ capabilities }: { capabilities: JsonRecord[] }) {
  return (
    <div className="ig-capability-table">
      {capabilities.map((capability, index) => {
        const metricKey = asText(capability.metric_key, "unknown metric");
        const level = asText(capability.metric_level, "ACCOUNT");
        const mediaType = asText(capability.media_type);
        const reason = asText(capability.reason, "unavailable");
        return (
          <div className="ig-capability-row" key={`${metricKey}-${mediaType}-${index}`}>
            <div className="ig-capability-name"><strong>{metricKey}</strong><span>{level}{mediaType ? ` · ${mediaType}` : ""}</span></div>
            <AvailabilityBadge reason={reason} />
          </div>
        );
      })}
    </div>
  );
}

export function DemoNotice({ fixtureVersion, children }: { fixtureVersion?: string; children?: React.ReactNode }) {
  return (
    <div className="ig-demo-notice">
      <div className="ig-demo-notice-icon"><WarningCircle size={18} weight="duotone" /></div>
      <div className="ig-demo-notice-copy">
        <strong>This is DEMO data, not a Live connection</strong>
        <span>{children || "Meta token remains server-only. Empty and unsupported metrics stay empty with a reason."}</span>
      </div>
      <span className="ig-demo-notice-version">{fixtureVersion || "instagram-growth-intelligence-v1.0"}</span>
    </div>
  );
}

export function PageError({ message }: { message: string }) {
  return (
    <div className="ig-error-state">
      <WarningCircle size={22} weight="duotone" />
      <div><strong>Instagram data could not be loaded</strong><span>{message}</span></div>
      <Link to="/instagram/data-health" className="ig-text-link">Open Data Health <ArrowRight size={14} /></Link>
    </div>
  );
}

export function LoadingState() {
  return <div className="ig-loading-state"><span className="ig-spinner" /><span>Loading Instagram read model…</span></div>;
}

export function RawMetricLabel({ label, value, source }: { label: string; value: number | null; source?: string }) {
  return (
    <div className="ig-raw-stat">
      <span>{label}</span>
      <strong>{formatNumber(value, { notation: "compact" })}</strong>
      {source ? <small>{source}</small> : null}
    </div>
  );
}

export function TrendValue({ value }: { value: number | null }) {
  return <span className={value === null ? "" : value >= 0 ? "ig-positive" : "ig-negative"}>{value === null ? "—" : `${value >= 0 ? "+" : ""}${formatPercent(value)}`}</span>;
}

export function derivedText(source: unknown, key: string, digits = 1) {
  return formatPercent(metricValue(source, key), digits);
}

export function metricReason(source: unknown, key: string) {
  const cell = metricCell(source, key);
  return asText(cell.reason, asText(cell.availability, "unavailable"));
}

export function contentEngagement(row: JsonRecord) {
  return metricValue(asRecord(row.derived), "engagement_rate_by_reach");
}

export function contentReach(row: JsonRecord) {
  return metricValue(asRecord(asRecord(row.raw).metrics), "reach") ?? 0;
}

export function contentRuleEvaluations(row: JsonRecord) {
  return Array.isArray(row.rule_evaluations) ? row.rule_evaluations.map(asRecord) : [];
}

export function contentId(row: JsonRecord, fallback: string) {
  return asText(asRecord(row.media).external_media_id, fallback);
}

export function contentTitle(row: JsonRecord) {
  return asText(asRecord(row.media).caption, "Untitled media");
}

export function contentType(row: JsonRecord) {
  return asText(asRecord(row.media).media_type, "MEDIA");
}

export function contentPublishedAt(row: JsonRecord) {
  return asRecord(row.media).published_at;
}

export function currentAccountMetric(model: ReturnType<typeof import("./instagramData").instagramReadModel>, key: string) {
  return metricValue(model.currentMetrics, key);
}

export function previousAccountMetric(model: ReturnType<typeof import("./instagramData").instagramReadModel>, key: string) {
  return metricValue(model.previousMetrics, key);
}

export function ruleStatus(row: JsonRecord) {
  const evaluation = contentRuleEvaluations(row)[0];
  return asText(evaluation?.status, "INSUFFICIENT_DATA");
}

export function ruleCode(row: JsonRecord) {
  const evaluation = contentRuleEvaluations(row)[0];
  return asText(evaluation?.rule_code, "BASELINE_PENDING");
}

export function mediaRawValue(row: JsonRecord, key: string) {
  return metricValue(asRecord(asRecord(row.raw).metrics), key);
}

export function mediaDerivedValue(row: JsonRecord, key: string) {
  return metricValue(asRecord(row.derived), key);
}

export function safeDelta(current: number | null, previous: number | null) {
  if (current === null || previous === null || previous === 0) return null;
  return (current - previous) / previous;
}

export function StatusIcon({ status }: { status: string }) {
  if (status === "available") return <ChartLineUp size={14} weight="bold" />;
  if (status === "permission_denied") return <LockKey size={14} weight="bold" />;
  return <Clock size={14} weight="bold" />;
}
