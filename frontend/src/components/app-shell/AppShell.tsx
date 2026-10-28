import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useScope } from "../../domain/scope";
import { ThemeSwitcher } from "../ThemeSwitcher";
import {
  Bell,
  CalendarBlank,
  CaretDown,
  ChartLineUp,
  FacebookLogo,
  FilmStrip,
  GearSix,
  GoogleLogo,
  House,
  InstagramLogo,
  LinkSimple,
  MagnifyingGlass,
  Plugs,
  Robot,
  ShoppingBag,
  Sparkle,
  TiktokLogo,
  UsersThree,
  YoutubeLogo,
} from "@phosphor-icons/react";

type SubNavItem = { to: string; label: string };
type NavGroup = { to: string; label: string; short: string; icon: string; children: readonly SubNavItem[] };

const NAV_GROUPS: readonly NavGroup[] = [
  {
    to: "/overview",
    label: "今日工作台",
    short: "工作台",
    icon: "pulse",
    children: [
      { to: "/overview", label: "今日概览" },
      { to: "/live", label: "实时监控" },
    ],
  },
  {
    to: "/accounts",
    label: "账号中心",
    short: "账号",
    icon: "accounts",
    children: [
      { to: "/accounts", label: "账号总览" },
    ],
  },
  {
    to: "/content",
    label: "内容中心",
    short: "内容",
    icon: "content",
    children: [
      { to: "/content", label: "内容表现" },
      { to: "/instagram", label: "Instagram 深度分析" },
      { to: "/creative", label: "创意实验室" },
    ],
  },
  {
    to: "/ads",
    label: "投放与转化",
    short: "投放",
    icon: "paid",
    children: [
      { to: "/ads", label: "投放概览" },
      { to: "/search", label: "搜索智能" },
      { to: "/funnel", label: "转化漏斗" },
    ],
  },
  {
    to: "/reviews",
    label: "决策中心",
    short: "决策",
    icon: "review",
    children: [
      { to: "/reviews", label: "数据复盘" },
      { to: "/focus", label: "重点监控" },
      { to: "/recommendations", label: "建议与机会" },
      { to: "/experiments", label: "实验记录" },
      { to: "/ai-console", label: "AI 洞察" },
    ],
  },
  {
    to: "/data-health",
    label: "数据与系统",
    short: "系统",
    icon: "database",
    children: [
      { to: "/data-health", label: "数据健康" },
      { to: "/settings/connections", label: "连接中心" },
      { to: "/execution/approvals", label: "执行与审计" },
      { to: "/execution/queue", label: "执行队列" },
      { to: "/execution/policies", label: "执行策略" },
      { to: "/execution/kill-switch", label: "安全开关" },
      { to: "/settings", label: "系统设置" },
    ],
  },
] as const;

const RANGE_OPTIONS = [
  { value: "YESTERDAY", label: "昨日" },
  { value: "LAST_7_DAYS", label: "近 7 天" },
  { value: "LAST_30_DAYS", label: "近 30 天" },
  { value: "THIS_MONTH", label: "本月" },
];

const INSTAGRAM_NAV_ITEMS = [
  { to: "/instagram", label: "Overview", icon: House },
  { to: "/instagram/content", label: "Content Intelligence", icon: FilmStrip },
  { to: "/instagram/audience", label: "Audience", icon: UsersThree },
  { to: "/instagram/insights", label: "AI Insights", icon: Sparkle },
  { to: "/instagram/data-health", label: "Connection / Data Health", icon: Plugs },
] as const;

function InstagramSideNav({ pathname }: { pathname: string }) {
  return (
    <aside className="instagram-side-nav">
      <Link to="/overview" className="instagram-brand-lockup">
        <span className="instagram-brand-mark"><ChartLineUp size={20} weight="bold" /></span>
        <span><strong>AI Growth</strong><small>Center</small></span>
      </Link>

      <button type="button" className="instagram-account-switcher" aria-label="Switch Instagram account">
        <span className="instagram-account-avatar"><InstagramLogo size={15} weight="fill" /></span>
        <span><strong>Vintage Audio</strong><small>Instagram workspace</small></span>
        <CaretDown size={14} />
      </button>

      <nav className="instagram-side-nav-section" aria-label="Instagram intelligence">
        <p className="instagram-side-nav-label">Instagram</p>
        {INSTAGRAM_NAV_ITEMS.map((item) => {
          const active = item.to === "/instagram"
            ? pathname === item.to
            : pathname === item.to || pathname.startsWith(`${item.to}/`);
          const Icon = item.icon;
          return (
            <Link key={item.to} to={item.to} className={`instagram-side-nav-item ${active ? "is-active" : ""}`}>
              <Icon size={17} weight={active ? "fill" : "regular"} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <nav className="instagram-side-nav-section" aria-label="Other channels">
        <p className="instagram-side-nav-label">Channels</p>
        <Link to="/ads" className="instagram-side-nav-item is-muted"><FacebookLogo size={17} /><span>Facebook Ads</span></Link>
        <Link to="/ads" className="instagram-side-nav-item is-muted"><GoogleLogo size={17} /><span>Google Ads</span></Link>
        <Link to="/content" className="instagram-side-nav-item is-muted"><YoutubeLogo size={17} /><span>YouTube</span></Link>
        <Link to="/content" className="instagram-side-nav-item is-muted"><TiktokLogo size={17} /><span>TikTok</span></Link>
      </nav>

      <nav className="instagram-side-nav-section" aria-label="Data sources">
        <p className="instagram-side-nav-label">Data</p>
        <Link to="/funnel" className="instagram-side-nav-item is-muted"><ShoppingBag size={17} /><span>Commerce</span></Link>
        <Link to="/data-health" className="instagram-side-nav-item is-muted"><LinkSimple size={17} /><span>UTM Tracking</span></Link>
      </nav>

      <div className="instagram-side-nav-bottom">
        <Link to="/settings" className="instagram-side-nav-item is-muted"><GearSix size={17} /><span>Settings</span></Link>
        <Link to="/settings/connections" className="instagram-side-nav-item is-muted"><Plugs size={17} /><span>Integrations</span></Link>
        <Link to="/ai-console" className="instagram-assistant-card">
          <span className="instagram-assistant-icon"><Robot size={18} weight="duotone" /></span>
          <span><strong>AI Assistant</strong><small>Ask about growth</small></span>
        </Link>
      </div>
    </aside>
  );
}

function InstagramTopbar({
  pathname,
  scope,
  setScope,
  navigate,
  isDemo,
}: {
  pathname: string;
  scope: { dateRange: string };
  setScope: (patch: { dateRange?: string }) => void;
  navigate: (to: string) => void;
  isDemo: boolean;
}) {
  const activeItem = INSTAGRAM_NAV_ITEMS.find((item) =>
    item.to === "/instagram" ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`),
  ) ?? INSTAGRAM_NAV_ITEMS[0];
  return (
    <header className="instagram-topbar">
      <div className="instagram-mobile-topbar-title">
        <Link to="/overview" className="instagram-mobile-logo"><ChartLineUp size={17} weight="bold" /></Link>
        <select aria-label="Instagram section" value={activeItem.to} onChange={(event) => navigate(event.target.value)}>
          {INSTAGRAM_NAV_ITEMS.map((item) => <option key={item.to} value={item.to}>{item.label}</option>)}
        </select>
      </div>
      <div className="instagram-topbar-context"><span>Growth workspace</span><strong>Instagram Intelligence</strong></div>
      <div className="instagram-topbar-actions">
        <label className="instagram-topbar-select">
          <CalendarBlank size={15} />
          <select aria-label="Date range" value={scope.dateRange} onChange={(event) => setScope({ dateRange: event.target.value })}>
            {RANGE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <CaretDown size={13} />
        </label>
        <span className={`instagram-topbar-demo ${isDemo ? "is-demo" : "is-live"}`}><span />{isDemo ? "Demo data" : "Live data"}</span>
        <button type="button" className="instagram-icon-button" aria-label="Search"><MagnifyingGlass size={17} /></button>
        <button type="button" className="instagram-icon-button has-notification" aria-label="Notifications"><Bell size={17} /><i /></button>
        <span className="instagram-user-avatar">VC</span>
      </div>
    </header>
  );
}

function NavIcon({ name }: { name: string }) {
  const paths: Record<string, React.ReactNode> = {
    pulse: <path d="M3 12h4l2-5 4 10 2-5h6" />,
    accounts: <><circle cx="9" cy="8" r="3" /><path d="M3.5 19c.7-4 3-6 5.5-6s4.8 2 5.5 6M16 7h5M18.5 4.5v5" /></>,
    content: <><rect x="4" y="4" width="16" height="16" rx="3" /><path d="m10 9 5 3-5 3Z" /></>,
    paid: <><path d="M4 19V5M4 19h16M8 15v-4M12 15V8M16 15V5" /></>,
    instagram: <><rect x="4" y="4" width="16" height="16" rx="5" /><circle cx="12" cy="12" r="3.5" /><circle cx="17.5" cy="6.5" r=".8" fill="currentColor" stroke="none" /></>,
    review: <><path d="M5 4h14v16H5z" /><path d="M8 8h8M8 12h8M8 16h5" /></>,
    database: <><ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v7c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 12v7c0 1.7 3.1 3 7 3s7-1.3 7-3v-7" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1A8 8 0 0 0 15 6l-.4-2.6h-4L10 6a8 8 0 0 0-1.5 1.1l-2.4-1-2 3.4L6.1 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1A8 8 0 0 0 10 18l.5 2.6h4L15 18a8 8 0 0 0 1.5-1.1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1Z" /></>,
  };
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { scope, accounts, setScope } = useScope();
  const [freshness, setFreshness] = useState<Array<Record<string, unknown>>>([]);
  const [environment, setEnvironment] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    void Promise.all([api.dataHealthFreshness(scope.workspaceId), api.healthSummary(scope.workspaceId)])
      .then(([health, summary]) => {
        setFreshness(health.sources ?? []);
        setEnvironment(summary);
      })
      .catch(() => {
        setFreshness([]);
        setEnvironment(null);
      });
  }, [scope.workspaceId]);

  const pathMatches = (pathname: string, to: string) => pathname === to || pathname.startsWith(`${to}/`);
  const activeGroup = useMemo(
    () => NAV_GROUPS.find((group) => pathMatches(location.pathname, group.to) || group.children.some((item) => pathMatches(location.pathname, item.to)) || (group.to === "/data-health" && location.pathname.startsWith("/execution/"))) ?? NAV_GROUPS[0],
    [location.pathname],
  );
  const activeItem = useMemo(
    () => activeGroup.children.find((item) => pathMatches(location.pathname, item.to)) ?? (location.pathname.startsWith("/execution/") ? activeGroup.children.find((item) => item.to.startsWith("/execution/")) : null) ?? activeGroup.children[0],
    [activeGroup, location.pathname],
  );
  const staleCount = freshness.filter((source) => !["FRESH", "DISABLED"].includes(String(source.status))).length;
  const dataMode = String(environment?.data_mode ?? "MOCK");
  const isDemo = dataMode === "MOCK" || String(environment?.environment ?? "local") !== "production";
  const workflowCounts = (environment?.workflow_counts ?? {}) as Record<string, number>;
  const activeEventCount = Number(workflowCounts.OPEN ?? 0) + Number(workflowCounts.IN_PROGRESS ?? 0);
  const isInstagramRoute = location.pathname.startsWith("/instagram");

  if (isInstagramRoute) {
    return (
      <div className="instagram-app-shell">
        <InstagramSideNav pathname={location.pathname} />
        <div className="instagram-shell-main">
          <InstagramTopbar
            pathname={location.pathname}
            scope={scope}
            setScope={setScope}
            navigate={navigate}
            isDemo={isDemo}
          />
          <main className="instagram-main">
            <div className="instagram-main-inner"><Outlet /></div>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 lg:flex">
      <aside className="hidden w-60 shrink-0 border-r border-[rgb(var(--sidebar-border))] bg-[rgb(var(--sidebar-bg))] lg:flex lg:min-h-screen lg:flex-col">
        <Link to="/overview" className="flex items-center gap-3 px-5 py-6">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500 text-sm font-bold text-white shadow-sm">R</span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-[rgb(var(--sidebar-active-fg))]">增长复盘中心</span>
            <span className="block text-[10px] uppercase tracking-[0.18em] text-[rgb(var(--sidebar-muted))]">Account health</span>
          </span>
        </Link>

        <div className="px-3">
          <p className="px-3 pb-2 text-[10px] font-medium uppercase tracking-[0.16em] text-[rgb(var(--sidebar-muted))]">当前分类</p>
          <nav className="space-y-1" aria-label={`${activeGroup.label}子导航`}>
            {activeGroup.children.map((item) => {
              const active = item.to === activeItem.to;
              return <Link key={item.to} to={item.to} className={`flex items-center rounded-xl px-3 py-2.5 text-sm transition-colors ${active ? "bg-[rgb(var(--sidebar-active-bg))] font-medium text-[rgb(var(--sidebar-active-fg))]" : "text-[rgb(var(--sidebar-fg))] hover:bg-[rgb(var(--sidebar-hover-bg))]"}`}>{item.label}</Link>;
            })}
          </nav>
        </div>

        <div className="mt-auto p-4">
          <div className="rounded-xl border border-[rgb(var(--sidebar-border))] bg-[rgb(var(--sidebar-bg))] p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-500">Safe mode</span>
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
            </div>
            <p className="mt-1 text-xs text-[rgb(var(--sidebar-fg))]">外部平台写入已禁用</p>
            <p className="mt-1 text-[10px] leading-relaxed text-[rgb(var(--sidebar-muted))]">当前只做检测、复盘与内部留痕。</p>
          </div>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/95 backdrop-blur">
          <div className="flex min-h-16 items-center gap-3 px-4 sm:px-6">
            <div className="flex min-w-0 items-center gap-3 lg:hidden">
              <Link to="/overview" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sky-500 text-xs font-bold text-white">R</Link>
              <select
                aria-label="页面导航"
                value={activeItem.to}
                onChange={(event) => navigate(event.target.value)}
                className="min-w-0 rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-sm text-slate-200"
              >
                {NAV_GROUPS.map((group) => <optgroup key={group.to} label={group.label}>{group.children.map((item) => <option key={item.to} value={item.to}>{item.label}</option>)}</optgroup>)}
              </select>
            </div>

            <div className="hidden min-w-0 lg:block">
              <p className="text-sm font-medium text-slate-200">{activeGroup.label}</p>
              <p className="text-[10px] text-slate-500">{activeItem.label} · {scope.workspaceId}</p>
            </div>

            <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
              <select
                aria-label="时间范围"
                value={scope.dateRange}
                onChange={(event) => setScope({ dateRange: event.target.value })}
                className="hidden rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-xs text-slate-300 sm:block"
              >
                {RANGE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
              <select
                aria-label="平台范围"
                value={scope.platforms[0] ?? ""}
                onChange={(event) => setScope({ platforms: event.target.value ? [event.target.value] : [], accountIds: [] })}
                className="hidden max-w-36 rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-xs text-slate-300 md:block"
              >
                <option value="">全部平台</option>
                {Array.from(new Set(accounts.map((account) => String(account.platform)))).map((platform) => <option key={platform} value={platform}>{platform}</option>)}
              </select>
              <select
                aria-label="账号范围"
                value={scope.accountIds.length > 1 ? "__MULTI__" : scope.accountIds[0] ?? ""}
                onChange={(event) => { if (event.target.value !== "__MULTI__") setScope({ accountIds: event.target.value ? [event.target.value] : [] }); }}
                className="hidden max-w-44 rounded-lg border border-slate-700 bg-slate-900 px-2 py-2 text-xs text-slate-300 xl:block"
              >
                <option value="">全部账号</option>
                {scope.accountIds.length > 1 ? <option value="__MULTI__">当前范围 · {scope.accountIds.length} 个账号</option> : null}
                {accounts.map((account) => <option key={String(account.id)} value={String(account.id)}>{String(account.platform)} @{String(account.username)}</option>)}
              </select>
              <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium ${isDemo ? "border-amber-500/30 bg-amber-500/10 text-amber-400" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${isDemo ? "bg-amber-400" : "bg-emerald-400"}`} />
                <span className="hidden sm:inline">{isDemo ? "演示数据" : "真实数据"}</span>
              </span>
              {staleCount > 0 ? <Link to="/data-health" className="hidden text-[10px] text-amber-400 sm:block">{staleCount} 个数据源异常</Link> : null}
              <Link
                to="/overview#exceptions"
                aria-label={`待处理异常 ${activeEventCount} 条`}
                className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-700 text-slate-400 hover:text-slate-200"
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></svg>
                {activeEventCount > 0 ? <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-rose-500 px-1 text-center text-[9px] leading-4 text-white">{activeEventCount}</span> : null}
              </Link>
              <div className="hidden sm:block"><ThemeSwitcher /></div>
            </div>
          </div>
          <nav className="hidden overflow-x-auto border-t border-slate-800/70 px-4 sm:px-6 lg:flex" aria-label="一级导航">
            <div className="flex min-w-max items-center gap-1">
              {NAV_GROUPS.map((group) => {
                const active = group.to === activeGroup.to;
                return <Link key={group.to} to={group.to} className={`flex min-h-11 items-center gap-2 border-b-2 px-3 text-xs transition-colors ${active ? "border-sky-400 text-sky-300" : "border-transparent text-slate-500 hover:border-slate-600 hover:text-slate-200"}`}><NavIcon name={group.icon} />{group.label}</Link>;
              })}
            </div>
          </nav>
        </header>

        <main className="min-w-0 overflow-x-hidden p-4 sm:p-6 xl:p-8">
          <div className="mx-auto w-full max-w-[1600px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
