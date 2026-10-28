import type {
  Alert,
  BrowserProfile,
  BrowserTask,
  EnvironmentOverview,
  ProfileDetail,
} from "../types";

const BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options?.headers as Record<string, string> | undefined) ?? {}),
    "X-User-Id": localStorage.getItem("codex_user_id") || "admin@recollect.test",
    "X-Workspace-Id": new URLSearchParams(path.split("?")[1] || "").get("workspace") || "ws_main",
  };
  const response = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.message || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  overview: () => request<EnvironmentOverview>("/environment/overview"),
  alerts: () => request<Alert[]>("/environment/alerts"),
  profiles: () => request<BrowserProfile[]>("/browser-profiles"),
  profile: (id: string) => request<ProfileDetail>(`/browser-profiles/${id}`),
  createProfile: (data: Record<string, unknown>) =>
    request<BrowserProfile>("/browser-profiles", { method: "POST", body: JSON.stringify(data) }),
  healthCheck: (id: string) =>
    request<BrowserTask>(`/browser-profiles/${id}/health-check`, { method: "POST" }),
  openProfile: (id: string) =>
    request<{ status: string }>(`/browser-profiles/${id}/open`, { method: "POST" }),
  closeProfile: (id: string) =>
    request<{ status: string }>(`/browser-profiles/${id}/close`, { method: "POST" }),
  createTask: (profileId: string, taskType: string, payload?: Record<string, unknown>) =>
    request<BrowserTask>("/browser-tasks", {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId, task_type: taskType, payload }),
    }),
  cancelTask: (id: string) =>
    request<BrowserTask>(`/browser-tasks/${id}/cancel`, { method: "POST" }),
  tasks: (profileId?: string) =>
    request<{ items: BrowserTask[]; total: number }>(
      `/browser-tasks${profileId ? `?profile_id=${profileId}` : ""}`,
    ),
  dataHealthFreshness: (workspaceId = "ws_main") =>
    request<{ sources: Array<Record<string, unknown>>; webhooks: Record<string, unknown> }>(
      `/data-health/freshness?workspace_id=${encodeURIComponent(workspaceId)}`,
    ),
  dataHealthQuality: (workspaceId = "ws_main") =>
    request<{ open_issues: Array<Record<string, unknown>>; total_open: number }>(
      `/data-health/quality?workspace_id=${encodeURIComponent(workspaceId)}`,
    ),
  dataHealthJobs: (workspaceId = "ws_main") =>
    request<Array<Record<string, unknown>>>(`/data-health/jobs?workspace_id=${encodeURIComponent(workspaceId)}`),
  metricsOverview: (startDate?: string, endDate?: string) =>
    request<Record<string, unknown>>(
      `/metrics/overview${startDate ? `?start_date=${startDate}&end_date=${endDate ?? ""}` : ""}`,
    ),
  ruleHealth: () => request<Record<string, unknown>>("/rule-health"),
  rules: () => request<Array<Record<string, unknown>>>("/rules"),
  recommendations: () => request<Array<Record<string, unknown>>>("/recommendations"),
  acknowledgeRecommendation: (id: string) =>
    request<Record<string, unknown>>(`/recommendations/${id}/acknowledge`, { method: "POST" }),
  approveRecommendation: (id: string) =>
    request<Record<string, unknown>>(`/recommendations/${id}/approve`, { method: "POST" }),
  rejectRecommendation: (id: string) =>
    request<Record<string, unknown>>(`/recommendations/${id}/reject`, { method: "POST" }),
  simulateRule: (ruleKey: string, candidateParameters: Record<string, unknown>, startDate: string, endDate: string) =>
    request<Record<string, unknown>>("/rule-simulations", {
      method: "POST",
      body: JSON.stringify({
        rule_key: ruleKey,
        candidate_parameters: candidateParameters,
        start_date: startDate,
        end_date: endDate,
      }),
    }),
  aiHealth: () => request<Record<string, unknown>>("/ai/health"),
  aiRuns: () => request<Array<Record<string, unknown>>>("/ai/runs"),
  aiRun: (id: string) => request<Record<string, unknown>>(`/ai/runs/${id}`),
  aiQuery: (query: string, scope: Record<string, unknown> = {}) =>
    request<Record<string, unknown>>("/ai/query", {
      method: "POST",
      body: JSON.stringify({ query, scope }),
    }),
  dashboardOverview: (startDate?: string, endDate?: string) =>
    request<Record<string, unknown>>(
      `/dashboard/overview${startDate ? `?start_date=${startDate}&end_date=${endDate ?? ""}` : ""}`,
    ),
  dashboardLive: () => request<Record<string, unknown>>("/dashboard/live"),
  adsCampaigns: (platform?: string) =>
    request<Array<Record<string, unknown>>>(`/ads/campaigns${platform ? `?platform=${platform}` : ""}`),
  adsCampaign: (id: string) => request<Record<string, unknown>>(`/ads/campaigns/${id}`),
  adsAdGroups: (platform?: string) =>
    request<Array<Record<string, unknown>>>(`/ads/ad-groups${platform ? `?platform=${platform}` : ""}`),
  adsAds: (platform?: string) =>
    request<Array<Record<string, unknown>>>(`/ads/ads${platform ? `?platform=${platform}` : ""}`),
  creatives: (lifecycle?: string) =>
    request<Array<Record<string, unknown>>>(`/creatives${lifecycle ? `?lifecycle=${lifecycle}` : ""}`),
  creative: (id: string) => request<Record<string, unknown>>(`/creatives/${id}`),
  creativeBriefs: () => request<Array<Record<string, unknown>>>("/creative-briefs"),
  searchTerms: () => request<Array<Record<string, unknown>>>("/search-intelligence/terms"),
  searchKeywords: () => request<Array<Record<string, unknown>>>("/search-intelligence/keywords"),
  searchNegatives: () => request<Array<Record<string, unknown>>>("/search-intelligence/negative-candidates"),
  searchExpansion: () => request<Array<Record<string, unknown>>>("/search-intelligence/expansion-candidates"),
  funnelOverview: () => request<Record<string, unknown>>("/funnel/overview"),
  experiments: () => request<Array<Record<string, unknown>>>("/experiments"),
  experiment: (id: string) => request<Record<string, unknown>>(`/experiments/${id}`),
  createExperiment: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/experiments", { method: "POST", body: JSON.stringify(data) }),
  settingsTargets: (workspaceId = "ws_main") =>
    request<Array<Record<string, unknown>>>(
      `/settings/business-targets?workspace_id=${encodeURIComponent(workspaceId)}`,
    ),
  updateSettingsTargets: (workspaceId: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(
      `/settings/business-targets?workspace_id=${encodeURIComponent(workspaceId)}`,
      { method: "PUT", body: JSON.stringify(data) },
    ),
  detectionRules: (workspaceId = "ws_main") =>
    request<Record<string, unknown>>(
      `/settings/detection-rules?workspace_id=${encodeURIComponent(workspaceId)}`,
    ),
  updateDetectionRules: (workspaceId: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(
      `/settings/detection-rules?workspace_id=${encodeURIComponent(workspaceId)}`,
      { method: "PUT", body: JSON.stringify(data) },
    ),
  notifications: () => request<Array<Record<string, unknown>>>("/notifications"),
  competitors: () => request<Record<string, unknown>>("/competitors"),

  // ---- PART 06-01: accounts / portfolio / content / focus / connections ----
  accounts: (workspaceId: string, platform?: string) =>
    request<Array<Record<string, unknown>>>(`/accounts?workspace_id=${workspaceId}${platform ? `&platform=${platform}` : ""}`),
  account: (id: string, workspaceId = "ws_main") =>
    request<Record<string, unknown>>(`/accounts/${id}?workspace_id=${encodeURIComponent(workspaceId)}`),
  accountOverview: (id: string, days = 30, workspaceId = "ws_main") =>
    request<Record<string, unknown>>(`/accounts/${id}/overview?days=${days}&workspace_id=${encodeURIComponent(workspaceId)}`),
  accountContent: (id: string, days = 30, workspaceId = "ws_main") =>
    request<Record<string, unknown>>(`/accounts/${id}/content?days=${days}&workspace_id=${encodeURIComponent(workspaceId)}`),
  accountCapabilities: (id: string, workspaceId = "ws_main") =>
    request<Record<string, unknown>>(`/accounts/${id}/capabilities?workspace_id=${encodeURIComponent(workspaceId)}`),
  refreshAccountCapabilities: (id: string) =>
    request<Record<string, unknown>>(`/accounts/${id}/refresh-capabilities`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  portfolioOverview: (workspaceId: string, platforms?: string, days = 30, accountIds = "") =>
    request<Record<string, unknown>>(
      `/portfolio/overview?workspace_id=${workspaceId}${platforms ? `&platforms=${platforms}` : ""}${accountIds ? `&account_ids=${accountIds}` : ""}&days=${days}`,
    ),
  portfolioContent: (workspaceId: string, accountIds = "", days = 30) =>
    request<Record<string, unknown>>(`/portfolio/content?workspace_id=${workspaceId}&account_ids=${accountIds}&days=${days}`),
  portfolioContentMatrix: (workspaceId: string, accountIds = "", days = 30) =>
    request<Record<string, unknown>>(`/portfolio/content-matrix?workspace_id=${workspaceId}&account_ids=${accountIds}&days=${days}`),
  contentList: (workspaceId: string) => request<Record<string, unknown>>(`/content?workspace_id=${workspaceId}`),
  contentAsset: (id: string) => request<Record<string, unknown>>(`/content/assets/${id}`),
  publication: (id: string, days = 30) => request<Record<string, unknown>>(`/content/publications/${id}?days=${days}`),
  publicationOrganic: (id: string) => request<Record<string, unknown>>(`/content/publications/${id}/organic`),
  publicationPaid: (id: string) => request<Record<string, unknown>>(`/content/publications/${id}/paid`),
  publicationPromotions: (id: string) => request<Record<string, unknown>>(`/content/publications/${id}/promotions`),
  createPromotionLink: (publicationId: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/content/publications/${publicationId}/promotion-links`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deletePromotionLink: (publicationId: string, linkId: string) =>
    request<Record<string, unknown>>(`/content/publications/${publicationId}/promotion-links/${linkId}`, { method: "DELETE" }),
  focusMonitors: (workspaceId: string) => request<Array<Record<string, unknown>>>(`/focus-monitors?workspace_id=${workspaceId}`),
  createFocusMonitor: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/focus-monitors", { method: "POST", body: JSON.stringify(data) }),
  focusMonitor: (id: string, days = 7) => request<Record<string, unknown>>(`/focus-monitors/${id}?days=${days}`),
  stopFocusMonitor: (id: string) => request<Record<string, unknown>>(`/focus-monitors/${id}/stop`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  watchlists: (workspaceId: string) => request<Array<Record<string, unknown>>>(`/focus-monitors/watchlists/list?workspace_id=${workspaceId}`),
  connections: (workspaceId: string) => request<Array<Record<string, unknown>>>(`/connections?workspace_id=${workspaceId}`),
  startOauth: (provider: string, workspaceId: string) =>
    request<Record<string, unknown>>(`/connections/${provider}/start-oauth`, {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, actor: "operator" }),
    }),
  validateConnection: (id: string) =>
    request<Record<string, unknown>>(`/connections/${id}/validate`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  discoverConnection: (id: string) =>
    request<Record<string, unknown>>(`/connections/${id}/discover`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  linkAccounts: (id: string, externalAccountIds: string[], workspaceId: string) =>
    request<Record<string, unknown>>(`/connections/${id}/link-accounts`, {
      method: "POST",
      body: JSON.stringify({ external_account_ids: externalAccountIds, workspace_id: workspaceId, actor: "operator" }),
    }),
  connectionHealth: (id: string) => request<Record<string, unknown>>(`/connections/${id}/health`),
  reauthorizeConnection: (id: string) =>
    request<Record<string, unknown>>(`/connections/${id}/reauthorize`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  providerCapabilities: () => request<Array<Record<string, unknown>>>("/provider-capabilities"),
  savedScopes: (workspaceId: string) => request<Array<Record<string, unknown>>>(`/saved-scopes?workspace_id=${workspaceId}`),
  createSavedScope: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/saved-scopes", { method: "POST", body: JSON.stringify(data) }),

  // ---- Instagram Growth Intelligence V1.0 (read-only, explicit DEMO until live sync lands) ----
  instagramOverview: (workspaceId = "ws_main", days = 28) =>
    request<Record<string, unknown>>(
      `/instagram/overview?workspace_id=${encodeURIComponent(workspaceId)}&days=${days}`,
    ),
  instagramCapabilities: (workspaceId = "ws_main") =>
    request<Record<string, unknown>>(
      `/instagram/capabilities?workspace_id=${encodeURIComponent(workspaceId)}`,
    ),
  instagramContent: (workspaceId = "ws_main", mediaType?: string) =>
    request<Record<string, unknown>>(
      `/instagram/content?workspace_id=${encodeURIComponent(workspaceId)}${mediaType ? `&media_type=${encodeURIComponent(mediaType)}` : ""}`,
    ),

  // ---- P0 account detection / business reviews ----
  healthSummary: (workspaceId: string) =>
    request<Record<string, unknown>>(`/health/summary?workspace_id=${encodeURIComponent(workspaceId)}`),
  accountHealthDetail: (accountId: string, workspaceId: string) =>
    request<Record<string, unknown>>(
      `/health/accounts/${accountId}?workspace_id=${encodeURIComponent(workspaceId)}`,
    ),
  updateHealthEvent: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/health/events/workflow", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  reviewPreview: (
    workspaceId: string,
    reviewType = "DAILY",
    accountIds: string[] = [],
    days?: number,
  ) => {
    const params = new URLSearchParams({ workspace_id: workspaceId, review_type: reviewType });
    if (accountIds.length) params.set("account_ids", accountIds.join(","));
    if (days) params.set("days", String(days));
    return request<Record<string, unknown>>(`/reviews/preview?${params.toString()}`);
  },
  reviewTrends: (workspaceId: string, days = 7, accountIds: string[] = []) => {
    const params = new URLSearchParams({ workspace_id: workspaceId, days: String(days) });
    if (accountIds.length) params.set("account_ids", accountIds.join(","));
    return request<Record<string, unknown>>(`/reviews/trends?${params.toString()}`);
  },
  reviewCampaigns: (
    workspaceId: string,
    reviewType = "DAILY",
    accountIds: string[] = [],
    days?: number,
  ) => {
    const params = new URLSearchParams({ workspace_id: workspaceId, review_type: reviewType });
    if (accountIds.length) params.set("account_ids", accountIds.join(","));
    if (days) params.set("days", String(days));
    return request<Record<string, unknown>>(`/reviews/campaigns?${params.toString()}`);
  },
  reviews: (workspaceId: string) =>
    request<Array<Record<string, unknown>>>(`/reviews?workspace_id=${encodeURIComponent(workspaceId)}`),
  review: (reviewId: string, workspaceId: string) =>
    request<Record<string, unknown>>(`/reviews/${reviewId}?workspace_id=${encodeURIComponent(workspaceId)}`),
  createReview: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/reviews", { method: "POST", body: JSON.stringify(data) }),
  createReviewFollowup: (reviewId: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/reviews/${reviewId}/followups`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateReviewFollowup: (followupId: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/reviews/followups/${followupId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  // ---- PART 06 execution console ----
  executionHealth: () => request<Record<string, unknown>>("/execution/health"),
  executionIntents: (status?: string) => request<Array<Record<string, unknown>>>(`/execution/intents${status ? `?status=${status}` : ""}`),
  executionIntent: (id: string) => request<Record<string, unknown>>(`/execution/intents/${id}`),
  executionApprovals: () => request<Array<Record<string, unknown>>>("/execution/approvals"),
  createExecutionApproval: (recommendationId: string) =>
    request<Record<string, unknown>>("/execution/approvals", {
      method: "POST",
      body: JSON.stringify({ recommendation_id: recommendationId, approved_by: "operator" }),
    }),
  approveExecutionApproval: (id: string) =>
    request<Record<string, unknown>>(`/execution/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  revokeExecutionApproval: (id: string) =>
    request<Record<string, unknown>>(`/execution/approvals/${id}/revoke`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  approveExecutionIntent: (id: string) =>
    request<Record<string, unknown>>(`/execution/intents/${id}/approve`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  rejectExecutionIntent: (id: string) =>
    request<Record<string, unknown>>(`/execution/intents/${id}/reject`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  executeExecutionIntent: (id: string) =>
    request<Record<string, unknown>>(`/execution/intents/${id}/execute`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  dryRunExecutionIntent: (id: string) =>
    request<Record<string, unknown>>(`/execution/intents/${id}/dry-run`, { method: "POST" }),
  executionJobs: (status?: string) => request<Array<Record<string, unknown>>>(`/execution/jobs${status ? `?status=${status}` : ""}`),
  executionJob: (id: string) => request<Record<string, unknown>>(`/execution/jobs/${id}`),
  retryExecutionJob: (id: string) =>
    request<Record<string, unknown>>(`/execution/jobs/${id}/retry`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  compensateExecutionJob: (id: string) =>
    request<Record<string, unknown>>(`/execution/jobs/${id}/compensate`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  executionPolicies: () => request<Array<Record<string, unknown>>>("/execution/policies"),
  createExecutionPolicy: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/execution/policies", { method: "POST", body: JSON.stringify(data) }),
  seedExecutionPolicies: () => request<Record<string, unknown>>("/execution/policies/seed", { method: "POST" }),
  killSwitches: () => request<Record<string, unknown>>("/execution/kill-switches"),
  enableGlobalKillSwitch: () =>
    request<Record<string, unknown>>("/execution/kill-switches/global/enable", { method: "POST", body: JSON.stringify({ actor: "admin", reason: "operator emergency stop" }) }),
  disableGlobalKillSwitch: () =>
    request<Record<string, unknown>>("/execution/kill-switches/global/disable", { method: "POST", body: JSON.stringify({ actor: "admin", reason: "resume operations" }) }),

  // ---- optimization pass: governance ----
  entities: (workspaceId: string, entityType?: string) =>
    request<Array<Record<string, unknown>>>(`/entities?workspace_id=${workspaceId}${entityType ? `&entity_type=${entityType}` : ""}`),
  createEntity: (data: Record<string, unknown>) => request<Record<string, unknown>>("/entities", { method: "POST", body: JSON.stringify(data) }),
  resolveExternalEntity: (entityId: string, provider: string) =>
    request<Record<string, unknown>>(`/entities/${entityId}/resolve-external?provider=${provider}`),
  metricDefinitions: () => request<Array<Record<string, unknown>>>("/metrics/definitions"),
  queryMetric: (data: Record<string, unknown>) => request<Record<string, unknown>>("/metrics/query", { method: "POST", body: JSON.stringify(data) }),
  recommendationCase: (id: string) => request<Record<string, unknown>>(`/recommendation-cases/${id}`),
  simulateCase: (id: string, parameters: Record<string, unknown> = {}) =>
    request<Record<string, unknown>>(`/recommendation-cases/${id}/simulate`, { method: "POST", body: JSON.stringify({ actor: "operator", parameters }) }),
  transitionCase: (id: string, target: string, reason?: string) =>
    request<Record<string, unknown>>(`/recommendation-cases/${id}/transition`, {
      method: "POST",
      body: JSON.stringify({ target, actor: "operator", reason }),
    }),
  draftCaseIntent: (id: string) =>
    request<Record<string, unknown>>(`/recommendation-cases/${id}/draft-intent`, { method: "POST", body: JSON.stringify({ actor: "operator" }) }),
  decisionAssistant: (workspaceId: string, userRequest: string, scope: Record<string, unknown> = {}) =>
    request<Record<string, unknown>>("/decision-assistant", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, user_request: userRequest, scope }),
    }),
  jobRegistry: () => request<Array<Record<string, unknown>>>("/job-registry"),
  providerManifests: () => request<Array<Record<string, unknown>>>("/provider-manifests"),
  credentialHealth: (workspaceId: string) => request<Record<string, unknown>>(`/credential-health?workspace_id=${workspaceId}`),
  authMe: () => request<Record<string, unknown>>("/auth/me"),
};
