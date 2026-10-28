import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  ChartLineUp,
  FilmStrip,
  Funnel,
  Info,
} from "@phosphor-icons/react";
import type { EChartsOption } from "echarts";
import { BaseChart } from "../components/charts/v2/BaseChart";
import {
  ContentCard,
  contentEngagement,
  contentId,
  contentReach,
  contentTitle,
  contentType,
  DataLayerBadge,
  DemoBadge,
  DemoNotice,
  EmptyMetric,
  InstagramSectionHeader,
  LoadingState,
  MetricTooltip,
  PageError,
  RawMetricLabel,
  mediaDerivedValue,
  mediaRawValue,
} from "./instagram/InstagramPrimitives";
import {
  asNumber,
  asRecord,
  asText,
  formatDate,
  instagramReadModel,
  useInstagramData,
} from "./instagram/instagramData";

const MEDIA_FILTERS = [
  ["ALL", "All content"],
  ["REELS", "Reels"],
  ["CAROUSEL_ALBUM", "Carousel"],
  ["IMAGE", "Posts"],
] as const;

type SortKey = "content_score" | "reach" | "engagement" | "shares" | "saves" | "follows";

function ContentMatrix({ rows }: { rows: Array<Record<string, unknown>> }) {
  const scoredRows = rows.filter((row) => asNumber(row.content_score) !== null);
  const option = useMemo<EChartsOption>(() => ({
    grid: { left: 58, right: 24, top: 24, bottom: 46 },
    tooltip: { trigger: "item" },
    xAxis: { type: "value", name: "Intent score", nameTextStyle: { color: "#8995a7", fontSize: 9 }, splitLine: { lineStyle: { color: "#202a38" } }, axisLabel: { color: "#778397", fontSize: 9 } },
    yAxis: { type: "value", name: "Content quality", nameTextStyle: { color: "#8995a7", fontSize: 9 }, splitLine: { lineStyle: { color: "#202a38" } }, axisLabel: { color: "#778397", fontSize: 9 } },
    series: [{
      type: "scatter",
      data: scoredRows.map((row) => {
        const derived = asRecord(row.derived);
        const raw = asRecord(asRecord(row.raw).metrics);
        return {
          name: contentTitle(row),
          value: [asNumber(row.intent_score) ?? 0, asNumber(row.content_score) ?? 0, mediaRawValue(row, "reach") ?? 0],
          symbolSize: Math.max(10, Math.min(42, Math.sqrt(Number(raw.reach || 0)) / 3)),
          itemStyle: { color: "#9b7bf4" },
          derived,
        };
      }),
    }],
  }), [scoredRows]);

  if (!scoredRows.length) {
    return (
      <div className="ig-matrix-empty">
        <ChartLineUp size={25} weight="duotone" color="#9274ed" />
        <strong>Content Matrix is withheld while the baseline calibrates</strong>
        <span>V1 requires a valid intent score, content quality score and enough same-type samples. The empty matrix is intentional; it is not a zero score.</span>
        <Link to="/instagram/data-health" className="ig-text-link">Review data requirements <ArrowRight size={14} /></Link>
      </div>
    );
  }
  return <BaseChart option={option} className="ig-chart" />;
}

function ContentDetail({ row, onClose }: { row: Record<string, unknown>; onClose: () => void }) {
  const media = asRecord(row.media);
  return (
    <section className="ig-panel">
      <InstagramSectionHeader
        eyebrow="Video / media detail"
        title={contentTitle(row)}
        description="Raw metrics, derived metrics, baseline state and optional AI creative analysis stay separate."
        action={<button type="button" className="instagram-outline-button" onClick={onClose}>Close detail</button>}
      />
      <div className="ig-inline-grid">
        <div className="ig-soft-card">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}><h3>Raw source metrics</h3><DataLayerBadge layer="RAW" /></div>
          <div className="ig-raw-stat-grid" style={{ marginTop: 12 }}>
            <RawMetricLabel label="Reach" value={mediaRawValue(row, "reach")} source="provider field: reach" />
            <RawMetricLabel label="Views" value={mediaRawValue(row, "views")} source="provider field: views" />
            <RawMetricLabel label="Shares" value={mediaRawValue(row, "shares")} source="provider field: shares" />
            <RawMetricLabel label="Saves" value={mediaRawValue(row, "saved")} source="provider field: saved" />
            <RawMetricLabel label="Follows" value={mediaRawValue(row, "follows")} source="provider field: follows" />
            <RawMetricLabel label="Profile visits" value={mediaRawValue(row, "profile_visits")} source="provider field: profile_visits" />
          </div>
        </div>
        <div className="ig-soft-card">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}><h3>Derived metrics</h3><DataLayerBadge layer="DERIVED" /></div>
          <div className="ig-raw-stat-grid" style={{ marginTop: 12 }}>
            <RawMetricLabel label="ER by reach" value={mediaDerivedValue(row, "engagement_rate_by_reach")} source="format: percent" />
            <RawMetricLabel label="Watch ratio" value={mediaDerivedValue(row, "watch_ratio")} source="duration-aware" />
            <RawMetricLabel label="Interactions" value={mediaDerivedValue(row, "engagement_count")} source="likes + comments + shares + saves" />
            <RawMetricLabel label="Content score" value={asNumber(row.content_score)} source="baseline pending" />
          </div>
        </div>
      </div>
      <div className="ig-detail-list" style={{ marginTop: 12 }}>
        <details className="ig-detail-item" open>
          <summary><span>Baseline and confidence</span><span className="ig-score-pill is-calibrating">CALIBRATING</span></summary>
          <p>Same-type content sample is below 10 records. Score, label and confidence are withheld; missing components are not filled with zero.</p>
        </details>
        <details className="ig-detail-item">
          <summary><span>Creative analysis</span><span className="ig-layer-badge is-ai">NOT RUN</span></summary>
          <p>AI creative analysis is a separate inference layer. It is not official API retention segmentation and is not generated from the current DEMO fixture.</p>
        </details>
        <details className="ig-detail-item">
          <summary><span>Experiment variables</span><span className="ig-layer-badge is-muted">1–3 VARIABLES</span></summary>
          <p>Once baseline is available, test one to three variables such as first-three-second hook, length or CTA. The current record does not have a causal experiment attached.</p>
        </details>
      </div>
      <div className="ig-panel-note"><Info size={14} /><span>{asText(media.media_type, "MEDIA")} · published {formatDate(media.published_at, true)} · raw payload ref {asText(asRecord(row.raw).raw_payload_ref, "fixture ref")}</span></div>
    </section>
  );
}

export function InstagramContent() {
  const { overview, content, loading, error } = useInstagramData(28);
  const [searchParams, setSearchParams] = useSearchParams();
  const [windowDays, setWindowDays] = useState<"7D" | "28D" | "90D">("28D");
  const [mediaFilter, setMediaFilter] = useState("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("reach");
  const model = instagramReadModel(overview, content);
  const selectedId = searchParams.get("media");
  const selectedRow = model.rows.find((row, index) => contentId(row, String(index)) === selectedId) ?? null;
  const filteredRows = useMemo(() => {
    const rows = model.rows.filter((row) => mediaFilter === "ALL" || contentType(row) === mediaFilter);
    return [...rows].sort((a, b) => {
      if (sortKey === "content_score") return (asNumber(b.content_score) ?? -1) - (asNumber(a.content_score) ?? -1);
      if (sortKey === "reach") return contentReach(b) - contentReach(a);
      if (sortKey === "engagement") return (contentEngagement(b) ?? -1) - (contentEngagement(a) ?? -1);
      return (mediaRawValue(b, sortKey) ?? -1) - (mediaRawValue(a, sortKey) ?? -1);
    });
  }, [mediaFilter, model.rows, sortKey]);

  if (loading && !overview) return <div className="instagram-page"><LoadingState /></div>;
  if (error && !overview) return <div className="instagram-page"><PageError message={error} /></div>;

  return (
    <div className="instagram-page">
      <header className="instagram-page-header">
        <div className="instagram-page-title">
          <div className="instagram-page-title-mark"><FilmStrip size={24} weight="duotone" /></div>
          <div><div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}><h1>Content Intelligence</h1><DemoBadge compact /></div><p>Rank organic content by traceable evidence, then open a single media detail.</p></div>
        </div>
        <div className="instagram-page-actions"><Link to="/instagram" className="instagram-outline-button">Back to overview <ArrowRight size={13} /></Link></div>
      </header>
      <DemoNotice fixtureVersion={asText(model.source.fixture_version)}>Paid metrics, revenue, ROAS and private competitor data are intentionally absent from this view.</DemoNotice>

      <div className="ig-filter-bar">
        <div className="ig-filter-group">
          <span className="ig-filter-label">Window</span>
          {(["7D", "28D", "90D"] as const).map((value) => <button type="button" key={value} className={`instagram-filter-button ${windowDays === value ? "is-active" : ""}`} onClick={() => setWindowDays(value)}>{value}</button>)}
        </div>
        <div className="ig-filter-group">
          <span className="ig-filter-label">Format</span>
          {MEDIA_FILTERS.map(([value, label]) => <button type="button" key={value} className={`instagram-filter-button ${mediaFilter === value ? "is-active" : ""}`} onClick={() => setMediaFilter(value)}>{label}</button>)}
        </div>
        <div className="ig-filter-group">
          <Funnel size={14} color="#78869a" />
          <select className="ig-select" aria-label="Sort content" value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
            <option value="content_score">Content score</option>
            <option value="reach">Reach</option>
            <option value="engagement">Engagement rate</option>
            <option value="shares">Shares</option>
            <option value="saved">Saves</option>
            <option value="follows">Follows</option>
          </select>
        </div>
      </div>

      {selectedRow ? <ContentDetail row={selectedRow} onClose={() => setSearchParams({})} /> : null}

      <div className="ig-split-layout">
        <section className="ig-panel">
          <InstagramSectionHeader eyebrow="Content ranking" title={`${filteredRows.length} records in view`} description="Default rank is reach because content score is still calibrating." action={<span className="ig-layer-badge is-derived">CONTENT SCORE V1.0</span>} />
          {filteredRows.length ? <div className="ig-content-grid">{filteredRows.map((row, index) => <ContentCard key={contentId(row, String(index))} row={row} index={index} />)}</div> : <EmptyMetric title="No content matched this filter" reason="An empty set remains empty; the system does not convert it to zero performance." />}
        </section>
        <section className="ig-panel">
          <InstagramSectionHeader eyebrow="Content matrix" title="Intent × quality" description="Bubble size is reach when the required scores exist." action={<MetricTooltip>Content Matrix axes come from derived Intent Score and Content Quality Score. Neither is inferred when the baseline is missing.</MetricTooltip>} />
          <ContentMatrix rows={filteredRows} />
        </section>
      </div>
    </div>
  );
}
