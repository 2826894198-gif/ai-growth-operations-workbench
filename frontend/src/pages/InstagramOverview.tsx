import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ChartLineUp,
  CursorClick,
  Eye,
  Heart,
  InstagramLogo,
  LinkSimple,
  LockKey,
  Sparkle,
  UsersThree,
} from "@phosphor-icons/react";
import type { EChartsOption } from "echarts";
import { BaseChart } from "../components/charts/v2/BaseChart";
import {
  ContentCard,
  DataLayerBadge,
  DemoBadge,
  DemoNotice,
  EmptyMetric,
  HealthPanel,
  InstagramSectionHeader,
  LoadingState,
  MetricCard,
  MetricTooltip,
  PageError,
} from "./instagram/InstagramPrimitives";
import {
  asRecord,
  asText,
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  instagramReadModel,
  metricCell,
  metricValue,
  safeDelta,
  useInstagramData,
} from "./instagram/instagramData";

function AccountTrendChart({
  currentMetrics,
  previousMetrics,
  currentAt,
  previousAt,
}: {
  currentMetrics: Record<string, unknown>;
  previousMetrics: Record<string, unknown>;
  currentAt: unknown;
  previousAt: unknown;
}) {
  const rows = useMemo(
    () => [
      {
        date: formatDate(previousAt),
        followers: metricValue(previousMetrics, "follower_count"),
        reach: metricValue(previousMetrics, "reach"),
      },
      {
        date: formatDate(currentAt),
        followers: metricValue(currentMetrics, "follower_count"),
        reach: metricValue(currentMetrics, "reach"),
      },
    ],
    [currentAt, currentMetrics, previousAt, previousMetrics],
  );
  const option = useMemo<EChartsOption>(() => ({
    grid: { left: 34, right: 18, top: 18, bottom: 26 },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#1b2432",
      borderColor: "#465267",
      textStyle: { color: "#e5e7eb", fontSize: 10 },
    },
    legend: { top: 0, right: 0, textStyle: { color: "#8592a5", fontSize: 9 } },
    xAxis: {
      type: "category",
      data: rows.map((row) => row.date),
      axisLine: { lineStyle: { color: "#2b3544" } },
      axisLabel: { color: "#778397", fontSize: 9 },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#1d2633" } },
      axisLabel: { color: "#6f7c8e", fontSize: 9 },
    },
    series: [
      {
        name: "Followers",
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        data: rows.map((row) => row.followers),
        lineStyle: { color: "#a78bfa", width: 2 },
        itemStyle: { color: "#a78bfa" },
      },
      {
        name: "Reach",
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        data: rows.map((row) => row.reach),
        lineStyle: { color: "#38bdf8", width: 2 },
        itemStyle: { color: "#38bdf8" },
      },
    ],
  }), [rows]);

  return <BaseChart option={option} className="ig-chart" />;
}

function InsightPanel({ model }: { model: ReturnType<typeof instagramReadModel> }) {
  const reach = metricValue(model.currentMetrics, "reach");
  const engagementRate = metricValue(model.derived, "engagement_rate_by_reach");
  const profileViews = metricValue(model.currentMetrics, "profile_views");
  const linkRate = metricValue(model.derived, "profile_link_tap_rate");
  return (
    <section className="ig-panel ig-insight-panel">
      <InstagramSectionHeader
        eyebrow="Priority insight"
        title="AI Growth Insight"
        description="Evidence-first summary. AI inference remains off until a Live evidence pack is available."
        action={<DemoBadge compact />}
      />
      <div className="ig-insight-body">
        <div className="ig-insight-lead">
          <div className="ig-insight-lead-top"><Sparkle size={15} weight="fill" /> Baseline is still calibrating</div>
          <h3>There is signal to inspect, but not enough history to call a winner.</h3>
          <p>Current reach and engagement are available for review. V1 will not turn a two-snapshot fixture into a confident growth claim.</p>
          <div className="ig-evidence-list">
            <div className="ig-evidence-item"><span>Reach</span><span>{formatNumber(reach, { notation: "compact" })}</span></div>
            <div className="ig-evidence-item"><span>Engagement rate</span><span>{formatPercent(engagementRate)}</span></div>
            <div className="ig-evidence-item"><span>Profile views</span><span>{formatNumber(profileViews, { notation: "compact" })}</span></div>
            <div className="ig-evidence-item"><span>Link tap rate</span><span>{formatPercent(linkRate)}</span></div>
          </div>
        </div>
        <div className="ig-insight-evidence">
          <div className="ig-evidence-block"><label>Decision state</label><strong>Calibrating</strong><small>History minimum not met</small></div>
          <div className="ig-evidence-block"><label>AI inference</label><strong>Not generated</strong><small>Needs evidence pack + confidence</small></div>
          <Link to="/instagram/insights" className="instagram-outline-button">Open AI Insights <ArrowRight size={14} /></Link>
        </div>
      </div>
      <div className="ig-insight-footer"><span>Raw and derived values remain separately traceable.</span><span>calculation instagram-v1.0</span></div>
    </section>
  );
}

function RecommendationPanel() {
  return (
    <section className="ig-panel ig-recommendation-panel">
      <div className="ig-recommendation-icon"><ChartLineUp size={17} weight="duotone" /></div>
      <h2 className="ig-recommendation-title">Build the missing baseline before scaling a creative formula.</h2>
      <ol className="ig-recommendation-steps">
        <li>Collect 21 valid account snapshot days.</li>
        <li>Reach at least 10 same-type content records.</li>
        <li>Connect Live Professional Insights when ready.</li>
      </ol>
      <Link to="/instagram/data-health" className="instagram-primary-button">Review connection readiness <ArrowRight size={14} /></Link>
    </section>
  );
}

function AudiencePreview() {
  return (
    <section className="ig-panel ig-audience-card">
      <InstagramSectionHeader
        eyebrow="Audience"
        title="Audience Target Fit"
        description="Persona and audience dimensions are permission-aware; unavailable is not zero."
        action={<Link to="/instagram/audience" className="instagram-outline-button">View audience <ArrowRight size={13} /></Link>}
      />
      <EmptyMetric
        title="Audience age / gender is not available"
        reason="The Demo fixture marks audience_age as permission_denied. No segment or interest label is inferred."
        action={<span className="ig-availability is-critical"><LockKey size={12} weight="bold" /> Permission required</span>}
      />
      <div className="ig-raw-stat-grid" style={{ marginTop: 12 }}>
        <div className="ig-raw-stat"><span>Audience fit</span><strong>—</strong><small>AI inference withheld</small></div>
        <div className="ig-raw-stat"><span>Top locations</span><strong>—</strong><small>not returned by fixture</small></div>
        <div className="ig-raw-stat"><span>Best time</span><strong>—</strong><small>needs ≥5 posts / slot</small></div>
      </div>
    </section>
  );
}

export function InstagramOverview() {
  const { overview, content, loading, error } = useInstagramData(28);
  const model = instagramReadModel(overview, content);
  const followerDelta = metricValue(model.derived, "follower_delta");
  const growthRate = metricValue(model.derived, "follower_growth_rate");
  const engagementRate = metricValue(model.derived, "engagement_rate_by_reach");
  const profileViews = metricValue(model.currentMetrics, "profile_views");
  const websiteClicks = metricValue(model.currentMetrics, "website_clicks");
  const linkTapSource = asText(metricCell(model.derived, "profile_link_tap_rate").source_metric, "website_clicks");
  const accountName = asText(model.account.display_name, "Instagram account");
  const username = asText(model.account.username, "—");
  const contentRows = model.rows.slice(0, 3);

  if (loading && !overview) return <div className="instagram-page"><LoadingState /></div>;
  if (error && !overview) return <div className="instagram-page"><PageError message={error} /></div>;

  return (
    <div className="instagram-page">
      <header className="instagram-page-header">
        <div className="instagram-page-title">
          <div className="instagram-page-title-mark"><InstagramLogo size={25} weight="fill" /></div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
              <h1>Instagram Dashboard</h1>
              {model.isDemo ? <DemoBadge compact /> : null}
            </div>
            <p><strong>@{username}</strong><span className="instagram-dot-separator">·</span>{asText(model.account.account_type, "CREATOR")}<span className="instagram-dot-separator">·</span>Last sync {formatDateTime(model.account.last_sync)}</p>
          </div>
        </div>
        <div className="instagram-page-actions">
          <Link to="/instagram/data-health" className="instagram-outline-button"><CursorClick size={14} /> Data health</Link>
          <Link to="/instagram/content" className="instagram-primary-button">Open content intelligence <ArrowRight size={14} /></Link>
        </div>
      </header>

      {error ? <PageError message={error} /> : null}
      <DemoNotice fixtureVersion={asText(model.source.fixture_version)}>
        Meta token stays server-side. This page renders the deterministic V1 fixture; Live sync, Ads, Revenue, ROAS and purchase attribution are not represented here.
      </DemoNotice>

      <section className="ig-kpi-section">
        <InstagramSectionHeader
          eyebrow="Growth overview"
          title={accountName}
          description="Six decision metrics defined in the V1 spec. Every value keeps its raw / derived provenance."
          action={<span className="ig-layer-badge is-raw">28D WINDOW</span>}
        />
        <div className="ig-kpi-grid">
          <MetricCard label="Followers" value={formatNumber(metricValue(model.currentMetrics, "follower_count"), { notation: "compact" })} detail="Current snapshot" source="RAW · follower_count" accent="violet" icon={<UsersThree size={14} />} trend={followerDelta === null ? undefined : `${followerDelta >= 0 ? "+" : ""}${formatNumber(followerDelta)}`} />
          <MetricCard label="Reach" value={formatNumber(metricValue(model.currentMetrics, "reach"), { notation: "compact" })} detail="28D account reach" source="RAW · reach" accent="blue" icon={<ChartLineUp size={14} />} trend={safeDelta(metricValue(model.currentMetrics, "reach"), metricValue(model.previousMetrics, "reach")) === null ? undefined : `${formatPercent(safeDelta(metricValue(model.currentMetrics, "reach"), metricValue(model.previousMetrics, "reach")))}`} />
          <MetricCard label="Engagement Rate" value={formatPercent(engagementRate)} detail="By reach" source="DERIVED · likes + comments + shares + saves" accent="green" icon={<Heart size={14} />} />
          <MetricCard label="Profile Views" value={formatNumber(profileViews, { notation: "compact" })} detail="28D account views" source="RAW · profile_views" accent="pink" icon={<Eye size={14} />} />
          <MetricCard label="Profile Link Taps" value={formatNumber(websiteClicks, { notation: "compact" })} detail="Explicit fallback shown" source={`RAW · ${linkTapSource}`} accent="orange" icon={<LinkSimple size={14} />} />
          <MetricCard label="Conversion Intent" value="—" detail="Connector not available" source="UNAVAILABLE · no purchase attribution" accent="slate" icon={<CursorClick size={14} />} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 7, color: "#778397", fontSize: 9 }}>
          <MetricTooltip>Formula: engagement rate by reach = (likes + comments + shares + saves) / reach. Profile link taps use profile_links_taps first, then website_clicks only as an explicit fallback.</MetricTooltip>
          <span>Derived rates are calculated server-side and are not official Meta fields.</span>
          {growthRate !== null ? <span className="ig-positive">Follower growth {formatPercent(growthRate)}</span> : null}
        </div>
      </section>

      <div className="ig-insight-grid">
        <InsightPanel model={model} />
        <RecommendationPanel />
      </div>

      <section className="ig-content-section">
        <InstagramSectionHeader
          eyebrow="Content intelligence"
          title="Top Content Performance"
          description="Ranked by available evidence. Content score remains withheld while the baseline is calibrating."
          action={<Link to="/instagram/content" className="instagram-outline-button">View all content <ArrowRight size={13} /></Link>}
        />
        {contentRows.length ? (
          <div className="ig-content-grid">
            {contentRows.map((row, index) => <ContentCard key={String(asRecord(row.media).external_media_id || index)} row={row} index={index} />)}
          </div>
        ) : (
          <EmptyMetric title="No content in the selected window" reason="The API returned an empty set. This is not treated as zero performance." />
        )}
        <div className="ig-content-section-footer">
          <p>{model.rows.length} DEMO records available · {Math.max(0, 5 - model.rows.length)} slots withheld until media is synced</p>
          <Link to="/instagram/content" className="ig-text-link">Open ranking and matrix <ArrowRight size={14} /></Link>
        </div>
      </section>

      <div className="ig-lower-grid">
        <HealthPanel health={model.health} />
        <AudiencePreview />
      </div>

      <section className="ig-panel">
        <InstagramSectionHeader
          eyebrow="Account trend"
          title="Observed account movement"
          description="Only the two raw snapshots present in the fixture are plotted. No missing dates are interpolated."
          action={<DataLayerBadge layer="RAW" />}
        />
        <AccountTrendChart currentMetrics={model.currentMetrics} previousMetrics={model.previousMetrics} currentAt={model.currentSnapshot.observed_at} previousAt={model.previousSnapshot.observed_at} />
      </section>
    </div>
  );
}
