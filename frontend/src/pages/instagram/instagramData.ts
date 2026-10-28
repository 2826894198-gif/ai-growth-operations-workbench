import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useScope } from "../../domain/scope";

export type JsonRecord = Record<string, unknown>;

export const DEMO_THUMBNAIL = "/instagram/demo-cassette-player.png";

export const asRecord = (value: unknown): JsonRecord =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as JsonRecord) : {};

export const asList = (value: unknown): JsonRecord[] =>
  Array.isArray(value) ? value.map(asRecord) : [];

export const asNumber = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

export const asText = (value: unknown, fallback = "") =>
  typeof value === "string" ? value : fallback;

export const metricCell = (source: unknown, key: string): JsonRecord =>
  asRecord(asRecord(source)[key]);

export const metricValue = (source: unknown, key: string): number | null => {
  const value = asRecord(source)[key];
  const rawValue = asNumber(value);
  return rawValue === null ? asNumber(metricCell(source, key).value) : rawValue;
};

export const formatNumber = (value: number | null, options?: Intl.NumberFormatOptions) =>
  value === null
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0, ...options }).format(value);

export const formatPercent = (value: number | null, digits = 1) =>
  value === null ? "—" : `${(value * 100).toFixed(digits)}%`;

export const formatDate = (value: unknown, withYear = false) => {
  const text = asText(value);
  if (!text) return "—";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    ...(withYear ? { year: "numeric" } : {}),
  }).format(date);
};

export const formatDateTime = (value: unknown) => {
  const text = asText(value);
  if (!text) return "—";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
};

export const mediaLabel = (value: unknown) => {
  const mediaType = asText(value, "MEDIA");
  if (mediaType === "CAROUSEL_ALBUM") return "CAROUSEL";
  return mediaType.replace(/_/g, " ");
};

export const availabilityLabel = (reason: string) => {
  switch (reason) {
    case "available":
      return "Available";
    case "permission_denied":
      return "Permission required";
    case "unsupported":
      return "Not supported";
    case "stale":
      return "Stale";
    default:
      return "Unavailable";
  }
};

export const availabilityTone = (reason: string) => {
  switch (reason) {
    case "available":
      return "is-available";
    case "permission_denied":
      return "is-critical";
    case "unsupported":
      return "is-muted";
    default:
      return "is-warning";
  }
};

export type InstagramData = {
  overview: JsonRecord | null;
  content: JsonRecord | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
};

export function useInstagramData(days = 28): InstagramData {
  const { scope } = useScope();
  const [overview, setOverview] = useState<JsonRecord | null>(null);
  const [content, setContent] = useState<JsonRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void Promise.all([
      api.instagramOverview(scope.workspaceId, days),
      api.instagramContent(scope.workspaceId),
    ])
      .then(([nextOverview, nextContent]) => {
        if (!active) return;
        setOverview(nextOverview);
        setContent(nextContent);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Instagram data failed to load");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [days, reloadKey, scope.workspaceId]);

  return {
    overview,
    content,
    loading,
    error,
    reload: () => setReloadKey((value) => value + 1),
  };
}

export function instagramReadModel(overview: JsonRecord | null, content: JsonRecord | null) {
  const account = asRecord(overview?.account);
  const source = asRecord(overview?.source);
  const raw = asRecord(overview?.raw);
  const currentSnapshot = asRecord(raw.current_account_snapshot);
  const previousSnapshot = asRecord(raw.previous_account_snapshot);
  const currentMetrics = asRecord(currentSnapshot.metrics);
  const previousMetrics = asRecord(previousSnapshot.metrics);
  const derived = asRecord(overview?.derived);
  const health = asRecord(overview?.health);
  const capabilities = asList(overview?.capabilities);
  const rows = asList(content?.rows);
  const caveats = Array.isArray(overview?.caveats) ? overview.caveats.map(String) : [];

  return {
    account,
    source,
    currentSnapshot,
    previousSnapshot,
    currentMetrics,
    previousMetrics,
    derived,
    health,
    capabilities,
    rows,
    caveats,
    requestedWindow: asNumber(overview?.requested_window_days) ?? 28,
    isDemo: asText(source.mode, "DEMO") === "DEMO" || source.is_live === false,
  };
}

export function safeDelta(current: number | null, previous: number | null) {
  if (current === null || previous === null || previous === 0) return null;
  return (current - previous) / previous;
}
