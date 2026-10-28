import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { DataBoundaryBanner } from "../components/common/DataBoundaryBanner";
import { ErrorState } from "../components/common/ErrorState";
import { HealthStatusBadge } from "../components/health/HealthStatusBadge";
import { Spinner } from "../components/Spinner";
import { useScope } from "../domain/scope";

type DataRecord = Record<string, unknown>;
type Segment = "ALL" | "COMPANY" | "EMPLOYEE" | "UNASSIGNED";

const RANK: Record<string, number> = { CRITICAL: 4, AT_RISK: 3, WARNING: 2, UNKNOWN: 1, HEALTHY: 0 };
const SEGMENT_LABELS: Record<Exclude<Segment, "ALL">, string> = {
  COMPANY: "公司账号",
  EMPLOYEE: "个人员工账号",
  UNASSIGNED: "待归类账号",
};

function text(value: unknown, fallback = "") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function number(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatNumber(value: unknown, digits = 0) {
  const parsed = number(value);
  return parsed == null ? "—" : parsed.toLocaleString("zh-CN", { maximumFractionDigits: digits });
}

function formatRatio(value: unknown) {
  const parsed = number(value);
  return parsed == null ? "—" : `${parsed.toFixed(2)}×`;
}

function formatPaidRatio(row: DataRecord) {
  const spend = number(row.paid_spend);
  return spend == null || spend <= 0 ? "—" : formatRatio(row.paid_roas);
}

function syncLabel(value: unknown) {
  if (!value) return "从未同步";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "未知";
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
}

function explicitSegment(row: DataRecord): Exclude<Segment, "ALL"> | null {
  const value = text(row.account_scope || row.owner_scope || row.segment).toUpperCase();
  if (["COMPANY", "BUSINESS", "CORPORATE"].includes(value)) return "COMPANY";
  if (["EMPLOYEE", "PERSONAL", "STAFF"].includes(value)) return "EMPLOYEE";
  if (["UNASSIGNED", "UNKNOWN"].includes(value)) return "UNASSIGNED";
  return null;
}

function inferSegment(row: DataRecord): { segment: Exclude<Segment, "ALL">; inferred: boolean } {
  const explicit = explicitSegment(row);
  if (explicit) return { segment: explicit, inferred: false };
  const accountType = text(row.account_type).toUpperCase();
  if (accountType.includes("CREATOR")) return { segment: "EMPLOYEE", inferred: true };
  if (["BUSINESS", "PAGE", "CHANNEL"].some((token) => accountType.includes(token))) return { segment: "COMPANY", inferred: true };
  return { segment: "UNASSIGNED", inferred: false };
}

function segmentNote(row: DataRecord) {
  const explicit = explicitSegment(row);
  if (explicit) return "已配置归属";
  const inferred = inferSegment(row);
  return inferred.inferred ? "按账号类型临时归类" : "等待 owner 映射";
}

function Metric({ label, value, hint, tone = "text-slate-100" }: { label: string; value: string; hint: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold tabular-nums ${tone}`}>{value}</p>
      <p className="mt-1 text-[10px] leading-relaxed text-slate-600">{hint}</p>
    </div>
  );
}

function AccountCard({
  account,
  selected,
  onToggleScope,
}: {
  account: DataRecord;
  selected: boolean;
  onToggleScope: (id: string) => void;
}) {
  const id = text(account.account_id || account.id);
  const statuses = (account.statuses ?? {}) as DataRecord;
  const inferred = inferSegment(account).inferred;
  const isTest = Boolean(account.is_test);
  return (
    <article className={`min-w-0 rounded-2xl border bg-slate-900/60 p-4 transition ${selected ? "border-sky-500/60 shadow-[0_0_0_1px_rgba(59,130,246,0.2)]" : "border-slate-800 hover:border-slate-700"}`}>
      <div className="flex items-start justify-between gap-3">
        <Link to={`/accounts/${id}`} className="flex min-w-0 items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-sm font-semibold text-slate-200">{text(account.username, "?").slice(0, 1).toUpperCase()}</span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-slate-100 hover:text-sky-400">@{text(account.username, "未知账号")}</span>
            <span className="mt-0.5 block truncate text-[10px] text-slate-500">{text(account.platform, "未知平台")} · {text(account.account_type, "类型未记录")}</span>
          </span>
        </Link>
        <HealthStatusBadge value={statuses.overall} compact />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-slate-700 bg-slate-950/30 px-2 py-1 text-[10px] text-slate-400">{text(account.owner_label, SEGMENT_LABELS[inferSegment(account).segment])}</span>
        {inferred ? <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-1 text-[10px] text-amber-400">临时归类</span> : null}
        {isTest ? <span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-2 py-1 text-[10px] text-violet-400">测试账号</span> : null}
        {account.is_primary ? <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-2 py-1 text-[10px] text-sky-400">主账号</span> : null}
      </div>

      <div className="mt-4 grid grid-cols-4 gap-2">
        {[["连接", statuses.connection], ["数据", statuses.data], ["经营", statuses.performance], ["内容", statuses.content]].map(([label, status]) => (
          <div key={String(label)} className="min-w-0 rounded-lg border border-slate-800 bg-slate-950/30 p-2">
            <p className="mb-1 text-[9px] text-slate-600">{String(label)}</p>
            <HealthStatusBadge value={status} compact />
          </div>
        ))}
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-slate-800 pt-3">
        <div><dt className="text-[9px] text-slate-600">浏览</dt><dd className="mt-1 text-sm tabular-nums text-slate-200">{formatNumber(account.views)}</dd></div>
        <div><dt className="text-[9px] text-slate-600">互动</dt><dd className="mt-1 text-sm tabular-nums text-slate-200">{formatNumber(account.engagements)}</dd></div>
        <div><dt className="text-[9px] text-slate-600">ROAS</dt><dd className="mt-1 text-sm tabular-nums text-slate-200">{formatPaidRatio(account)}</dd></div>
      </dl>

      <div className="mt-4 flex items-center justify-between gap-3">
        <span className="min-w-0 truncate text-[10px] text-slate-600" title={segmentNote(account)}>{segmentNote(account)} · {syncLabel(account.last_sync_at)}</span>
        <button type="button" onClick={() => onToggleScope(id)} className={`min-h-10 shrink-0 rounded-lg border px-3 py-2 text-[11px] transition ${selected ? "border-sky-500/50 bg-sky-500/10 text-sky-300" : "border-slate-700 text-slate-400 hover:border-sky-500/50 hover:text-sky-300"}`} aria-pressed={selected}>{selected ? "移出范围" : "加入范围"}</button>
      </div>
    </article>
  );
}

export function Accounts() {
  const { scope, setScope, accounts: directory } = useScope();
  const [health, setHealth] = useState<DataRecord | null>(null);
  const [portfolio, setPortfolio] = useState<DataRecord | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [segment, setSegment] = useState<Segment>("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const accountIds = scope.accountIds.join(",");
  const platforms = scope.platforms.join(",");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const [healthResult, portfolioResult] = await Promise.allSettled([
      api.healthSummary(scope.workspaceId),
      api.portfolioOverview(scope.workspaceId, platforms, 30, accountIds),
    ]);
    if (healthResult.status === "fulfilled") setHealth(healthResult.value);
    if (portfolioResult.status === "fulfilled") setPortfolio(portfolioResult.value);
    if (healthResult.status === "rejected" && portfolioResult.status === "rejected") setError("账号数据加载失败，请检查连接和后端状态。");
    setLoading(false);
  }, [accountIds, platforms, scope.workspaceId]);

  useEffect(() => { void load(); }, [load]);

  const healthRows = (health?.accounts ?? []) as DataRecord[];
  const metricRows = (portfolio?.accounts ?? []) as DataRecord[];
  const metricMap = useMemo(() => new Map(metricRows.map((row) => [text(row.id), row])), [metricRows]);
  const healthMap = useMemo(() => new Map(healthRows.map((row) => [text(row.account_id), row])), [healthRows]);
  const directoryMap = useMemo(() => new Map(directory.map((row) => [text(row.id), row])), [directory]);

  const allRows = useMemo<DataRecord[]>(() => {
    const ids = new Set([...directoryMap.keys(), ...healthMap.keys(), ...metricMap.keys()]);
    return Array.from(ids).map((id) => {
      const row = { ...(directoryMap.get(id) ?? {}), ...(healthMap.get(id) ?? {}), ...(metricMap.get(id) ?? {}) };
      const classification = inferSegment(row);
      return { ...row, account_id: id, __segment: classification.segment, __inferred: classification.inferred };
    });
  }, [directoryMap, healthMap, metricMap]);

  const platformRows = useMemo(() => {
    const scopedRows = scope.accountIds.length ? allRows.filter((row) => scope.accountIds.includes(text(row.account_id))) : allRows;
    const selectedPlatform = scope.platforms[0];
    return selectedPlatform ? scopedRows.filter((row) => text(row.platform).toUpperCase() === selectedPlatform.toUpperCase()) : scopedRows;
  }, [allRows, scope.accountIds, scope.platforms]);

  const channelOptions = useMemo(
    () => Array.from(new Set(allRows.map((row) => text(row.platform).toUpperCase()).filter(Boolean))).sort(),
    [allRows],
  );

  const rows = useMemo(() => platformRows.filter((row) => {
    const statuses = (row.statuses ?? {}) as DataRecord;
    const matchesSegment = segment === "ALL" || row.__segment === segment;
    const matchesStatus = statusFilter === "ALL" || text(statuses.overall, "UNKNOWN") === statusFilter;
    const haystack = `${text(row.username)} ${text(row.display_name)} ${text(row.platform)} ${text(row.owner_label)}`.toLowerCase();
    return matchesSegment && matchesStatus && haystack.includes(query.trim().toLowerCase());
  }).sort((a, b) => (RANK[text(((b.statuses ?? {}) as DataRecord).overall, "UNKNOWN")] ?? 1) - (RANK[text(((a.statuses ?? {}) as DataRecord).overall, "UNKNOWN")] ?? 1)), [platformRows, query, segment, statusFilter]);

  const groupedRows = useMemo(() => {
    const segmentBuckets = new Map<string, DataRecord[]>();
    for (const row of rows) {
      const key = text(row.__segment, "UNASSIGNED").toUpperCase();
      segmentBuckets.set(key, [...(segmentBuckets.get(key) ?? []), row]);
    }
    return (["COMPANY", "EMPLOYEE", "UNASSIGNED"] as const)
      .map((key) => {
        const segmentRows = segmentBuckets.get(key) ?? [];
        const ownerBuckets = new Map<string, DataRecord[]>();
        for (const row of segmentRows) {
          const owner = text(row.account_group_name || row.group_name || row.owner_label, "未命名归属");
          ownerBuckets.set(owner, [...(ownerBuckets.get(owner) ?? []), row]);
        }
        return { key, rows: segmentRows, ownerGroups: Array.from(ownerBuckets.entries()) };
      })
      .filter((group) => group.rows.length > 0);
  }, [rows]);

  const portfolioKpis = (portfolio?.kpis ?? {}) as DataRecord;
  const kpiValue = (key: string) => {
    const value = portfolioKpis[key];
    return value && typeof value === "object" ? (value as DataRecord).value : null;
  };
  const selectedIds = new Set(scope.accountIds);
  const usableCount = platformRows.filter((row) => Boolean(row.data_usable)).length;
  const criticalCount = platformRows.filter((row) => text(((row.statuses ?? {}) as DataRecord).overall) === "CRITICAL").length;
  const inferredCount = platformRows.filter((row) => Boolean(row.__inferred)).length;
  const mappingNote = inferredCount
    ? `当前范围有 ${inferredCount} 个账号尚未显式映射 owner；Creator / Business 类型只作临时分组。`
    : "当前范围账号均已显式映射 owner；后续可在账号组配置中维护归属。";

  const toggleScope = (id: string) => {
    const next = selectedIds.has(id) ? scope.accountIds.filter((value) => value !== id) : [...scope.accountIds, id];
    setScope({ accountIds: next });
  };

  if (loading && !health && !portfolio) return <Spinner />;

  return (
    <div className="space-y-5 pb-8 sm:space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-sky-400">Account center</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">账号中心</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-500">先选择渠道，再按公司账号、个人员工账号和待归类账号查看连接、数据、经营与内容状态。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {scope.accountIds.length ? <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-3 py-2 text-xs text-sky-300">当前范围 {scope.accountIds.length} 个账号</span> : <span className="text-xs text-slate-500">当前范围：全部账号</span>}
          <button type="button" onClick={() => void load()} className="min-h-10 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:border-sky-500 hover:text-sky-300">重新检测</button>
          <Link to="/settings/connections" className="inline-flex min-h-10 items-center rounded-lg bg-sky-500 px-4 py-2 text-xs font-medium text-white transition hover:bg-sky-400">管理连接</Link>
        </div>
      </header>

      {error ? <ErrorState message={error} /> : null}
      <DataBoundaryBanner dataMode={health?.data_mode} dataUsable={Boolean(health?.data_usable)} evaluatedAt={health?.evaluated_at} blockingReasons={(health?.blocking_reasons ?? []) as unknown[]} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <Metric label="当前账号" value={formatNumber(platformRows.length)} hint={scope.platforms.length ? `${scope.platforms.join("、")} 渠道` : "全部已连接账号"} />
        <Metric label="可用于复盘" value={formatNumber(usableCount)} hint="数据可用状态" tone="text-emerald-400" />
        <Metric label="严重问题" value={formatNumber(criticalCount)} hint="当前范围需要先处理" tone="text-rose-400" />
        <Metric label="自然浏览" value={formatNumber(kpiValue("views"))} hint="平台事件合计" />
        <Metric label="付费花费" value={kpiValue("paid_spend") == null ? "—" : `$${formatNumber(kpiValue("paid_spend"), 2)}`} hint="当前账号范围" />
        <Metric label="归属待确认" value={formatNumber(inferredCount)} hint={inferredCount ? "按账号类型临时归类" : "owner 已显式映射"} tone="text-amber-400" />
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[240px_minmax(0,1fr)] xl:items-start">
        <aside className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <div><h2 className="text-sm font-semibold text-slate-200">账号层级</h2><p className="mt-1 text-[10px] text-slate-600">按归属切换视图</p></div>
            {segment !== "ALL" ? <button type="button" onClick={() => setSegment("ALL")} className="text-[10px] text-sky-400">清除</button> : null}
          </div>
          <div className="mt-4 space-y-1">
            {(["ALL", "COMPANY", "EMPLOYEE", "UNASSIGNED"] as Segment[]).map((key) => {
              const count = key === "ALL" ? platformRows.length : platformRows.filter((row) => row.__segment === key).length;
              const label = key === "ALL" ? "全部账号" : SEGMENT_LABELS[key];
              return <button key={key} type="button" onClick={() => setSegment(key)} className={`flex min-h-11 w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs transition ${segment === key ? "bg-sky-500/10 text-sky-300" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"}`}><span>{label}</span><span className="tabular-nums text-[10px] text-slate-600">{count}</span></button>;
            })}
          </div>
          <div className="mt-6 border-t border-slate-800 pt-4">
            <h3 className="text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">渠道</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={() => setScope({ platforms: [], accountIds: [] })} className={`min-h-9 rounded-lg border px-3 py-2 text-[11px] transition ${!scope.platforms.length ? "border-sky-500/50 bg-sky-500/10 text-sky-300" : "border-slate-700 text-slate-500 hover:text-slate-300"}`}>全部</button>
              {channelOptions.map((channel) => <button type="button" key={channel} onClick={() => setScope({ platforms: [channel], accountIds: [] })} className={`min-h-9 rounded-lg border px-3 py-2 text-[11px] transition ${scope.platforms[0] === channel ? "border-sky-500/50 bg-sky-500/10 text-sky-300" : "border-slate-700 text-slate-500 hover:text-slate-300"}`}>{channel}</button>)}
            </div>
          </div>
          <div className={`mt-6 rounded-xl border p-3 text-[10px] leading-relaxed ${inferredCount ? "border-amber-500/20 bg-amber-500/5 text-amber-300/80" : "border-emerald-500/20 bg-emerald-500/5 text-emerald-300/80"}`}>{mappingNote}</div>
        </aside>

        <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60">
          <div className="flex flex-col gap-3 border-b border-slate-800 p-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <div><h2 className="text-sm font-semibold text-slate-200">账号列表</h2><p className="mt-1 text-xs text-slate-500">{rows.length} 个结果 · 点击卡片进入账号详情，加入范围后会同步到全局筛选。</p></div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索账号、平台或 owner" aria-label="搜索账号、平台或 owner" className="min-h-10 min-w-0 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200 outline-none focus:border-sky-500 sm:w-56" />
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="账号健康状态" className="min-h-10 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-300"><option value="ALL">全部状态</option><option value="CRITICAL">严重</option><option value="AT_RISK">高风险</option><option value="WARNING">需观察</option><option value="HEALTHY">正常</option><option value="UNKNOWN">未知</option></select>
            </div>
          </div>

          <div className="space-y-5 p-4 sm:p-5">
            {groupedRows.map(({ key, rows: segmentRows, ownerGroups }) => <section key={key}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div><h3 className="text-xs font-semibold text-slate-200">{SEGMENT_LABELS[key]}</h3><p className="mt-1 text-[10px] text-slate-600">{segmentRows.length} 个账号 · {Array.from(new Set(segmentRows.map((row) => text(row.platform).toUpperCase()).filter(Boolean))).join("、") || "多渠道"}</p></div>
                <span className="text-[10px] text-slate-600">{segment === "ALL" ? "可切换层级" : "当前层级"}</span>
              </div>
              <div className="space-y-4">
                {ownerGroups.map(([owner, ownerRows]) => <div key={`${key}-${owner}`}>
                  {ownerGroups.length > 1 ? <div className="mb-2 flex items-center justify-between gap-2"><h4 className="text-[11px] font-medium text-slate-300">{owner}</h4><span className="text-[10px] text-slate-600">{ownerRows.length} 个账号</span></div> : null}
                  <div className="grid min-w-0 gap-3 2xl:grid-cols-2">{ownerRows.map((account) => <AccountCard key={text(account.account_id)} account={account} selected={selectedIds.has(text(account.account_id))} onToggleScope={toggleScope} />)}</div>
                </div>)}
              </div>
            </section>)}
            {!groupedRows.length ? <div className="rounded-xl border border-dashed border-slate-700 px-5 py-14 text-center"><p className="text-sm text-slate-300">没有符合当前层级或筛选的账号</p><p className="mt-1 text-xs text-slate-600">可以清除筛选，或前往连接设置添加账号。</p><Link to="/settings/connections" className="mt-4 inline-flex min-h-10 items-center text-xs text-sky-400">管理连接 →</Link></div> : null}
          </div>
        </section>
      </div>
    </div>
  );
}
