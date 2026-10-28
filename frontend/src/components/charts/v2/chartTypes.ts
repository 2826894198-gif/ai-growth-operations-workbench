export type ChartStatus =
  | "ready"
  | "loading"
  | "empty"
  | "partial"
  | "stale"
  | "not_connected"
  | "error";

export interface ChartQuality {
  status?: ChartStatus;
  source?: string;
  freshness?: string | null;
  completeness?: number | null;
  sampleSize?: number | null;
  comparableSampleSize?: number | null;
  caveat?: string | null;
  error?: string | null;
}
