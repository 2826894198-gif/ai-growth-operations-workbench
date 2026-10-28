export interface Kpi {
  key: string;
  label: string;
  value: number | null;
  format: "currency" | "percent" | "ratio" | "integer";
  positive_direction: "up" | "down";
  compare_pct?: number | null;
  target?: number | null;
  status: "GOOD" | "WATCH" | "BAD" | "UNKNOWN";
}

export interface OverviewRecommendation {
  id: string;
  entity_type: string;
  entity_id: string;
  platform?: string | null;
  primary_action: string;
  reason_group: string;
  severity: string;
  confidence: number;
  evidence: Array<Record<string, unknown>>;
}

export interface DashboardOverview {
  business_status: string;
  kpis: Kpi[];
  recommendations: OverviewRecommendation[];
  platforms: Array<Record<string, unknown>>;
  trend: Array<{ date: string; spend: number; net_revenue: number; blended_roas: number | null }>;
  highlights: Record<string, unknown>;
  daily_brief: Record<string, unknown>;
  freshness: Array<Record<string, unknown>>;
}

export interface CampaignRow {
  id: string;
  campaign_id: string;
  name: string;
  platform: string;
  status?: string | null;
  spend: number;
  impressions: number;
  clicks: number;
  ctr?: number | null;
  conversions: number;
  cpa?: number | null;
  platform_roas?: number | null;
  rule_result?: string;
}

export interface CreativeRow {
  creative_id: string;
  name?: string | null;
  title?: string | null;
  platform: string;
  thumbnail_url?: string | null;
  spend_30d: number;
  purchases_30d: number;
  roas_30d?: number | null;
}

export interface SearchTermRow {
  term: string;
  spend: number;
  clicks: number;
  conversions: number;
  cpa?: number | null;
  intent: string;
  commercial_relevance: string;
}
