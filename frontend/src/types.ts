export interface ProxyInfo {
  id: string;
  provider: string;
  proxy_type: string;
  host: string;
  port: number;
  country?: string | null;
  region?: string | null;
  city?: string | null;
  is_static: boolean;
  status: string;
  last_ip?: string | null;
  last_checked_at?: string | null;
  latency_ms?: number | null;
}

export interface BrowserProfile {
  id: string;
  provider: string;
  provider_profile_id?: string | null;
  profile_no?: string | null;
  name: string;
  profile_type: string;
  platform?: string | null;
  proxy_id?: string | null;
  proxy?: ProxyInfo | null;
  country?: string | null;
  region?: string | null;
  city?: string | null;
  timezone?: string | null;
  language?: string | null;
  browser_engine?: string | null;
  os_type?: string | null;
  fingerprint_config?: Record<string, unknown> | null;
  status: string;
  health?: string | null;
  last_health_check_at?: string | null;
  last_opened_at?: string | null;
  last_closed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BrowserTask {
  id: string;
  profile_id: string;
  task_type: string;
  task_name?: string | null;
  status: string;
  payload?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  started_at?: string | null;
  finished_at?: string | null;
  retry_count: number;
  error_code?: string | null;
  error_message?: string | null;
  screenshot_path?: string | null;
  log_path?: string | null;
  created_at: string;
}

export interface HealthCheck {
  id: string;
  profile_id: string;
  status: string;
  public_ip?: string | null;
  country?: string | null;
  timezone?: string | null;
  language?: string | null;
  proxy_latency_ms?: number | null;
  browser_launch_ms?: number | null;
  checks?: Record<string, unknown> | null;
  created_at: string;
}

export interface EnvironmentOverview {
  total_profiles: number;
  healthy_profiles: number;
  unhealthy_profiles: number;
  running_browsers: number;
  queued_tasks: number;
  failed_tasks: number;
}

export interface Alert {
  severity: string;
  code: string;
  message: string;
  profile_id?: string | null;
  profile_name?: string | null;
  created_at: string;
}

export interface ProfileDetail extends BrowserProfile {
  audits: Array<Record<string, unknown>>;
  health_checks: HealthCheck[];
  recent_tasks: BrowserTask[];
}
