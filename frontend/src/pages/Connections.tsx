import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useScope } from "../domain/scope";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";
import { HealthStatusBadge } from "../components/health/HealthStatusBadge";

export function Connections() {
  const { scope, refreshAccounts } = useScope();
  const [tab, setTab] = useState<"connections" | "targets" | "detection" | "metrics">("connections");
  const [connections, setConnections] = useState<Array<Record<string, unknown>>>([]);
  const [capabilities, setCapabilities] = useState<Array<Record<string, unknown>>>([]);
  const [targets, setTargets] = useState<Record<string, string>>({});
  const [detectionRules, setDetectionRules] = useState<Record<string, number>>({});
  const [metricDefinitions, setMetricDefinitions] = useState<Array<Record<string, unknown>>>([]);
  const [discovered, setDiscovered] = useState<Record<string, unknown> | null>(null);
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [messageError, setMessageError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rows, caps, targetRows, rules, definitions] = await Promise.all([
        api.connections(scope.workspaceId),
        api.providerCapabilities(),
        api.settingsTargets(scope.workspaceId),
        api.detectionRules(scope.workspaceId),
        api.metricDefinitions(),
      ]);
      setConnections(rows);
      setCapabilities(caps);
      const target = targetRows[0] ?? {};
      setTargets(Object.fromEntries([
        "target_roas",
        "break_even_roas",
        "target_cpa",
        "target_aov",
        "max_daily_spend",
        "max_campaign_daily_spend",
        "refund_rate_warning",
      ].map((key) => [key, target[key] == null ? "" : String(target[key])])));
      setDetectionRules({
        sync_delay_minutes: Number(rules.sync_delay_minutes ?? 20),
        sync_stale_minutes: Number(rules.sync_stale_minutes ?? 60),
        content_inactive_days: Number(rules.content_inactive_days ?? 7),
      });
      setMetricDefinitions(definitions);
    } finally {
      setLoading(false);
    }
  }, [scope.workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  const discover = async (id: string) => {
    const result = await api.discoverConnection(id);
    setDiscovered(result);
    setSelectedAccounts([]);
  };

  const link = async (id: string) => {
    if (!selectedAccounts.length) return;
    await api.linkAccounts(id, selectedAccounts, scope.workspaceId);
    setDiscovered(null);
    await load();
    await refreshAccounts();
  };

  const validate = async (id: string) => {
    await api.validateConnection(id);
    await load();
  };

  const reauthorize = async (id: string) => {
    await api.reauthorizeConnection(id);
    await load();
  };

  const saveTargets = async () => {
    setSaving(true);
    setMessage("");
    setMessageError(false);
    try {
      await api.updateSettingsTargets(scope.workspaceId, Object.fromEntries(
        Object.entries(targets).filter(([, value]) => value !== "").map(([key, value]) => [key, Number(value)]),
      ));
      setMessage("业务目标已保存");
    } catch (reason) {
      setMessageError(true);
      setMessage(reason instanceof Error ? reason.message : "业务目标保存失败");
    } finally {
      setSaving(false);
    }
  };

  const saveDetectionRules = async () => {
    setSaving(true);
    setMessage("");
    setMessageError(false);
    try {
      await api.updateDetectionRules(scope.workspaceId, detectionRules);
      setMessage("账号检测规则已保存，将用于下一次检测");
    } catch (reason) {
      setMessageError(true);
      setMessage(reason instanceof Error ? reason.message : "检测规则保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading && !connections.length) return <Spinner />;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-sky-400">Workspace settings</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">设置</h1>
        <p className="mt-1 text-sm text-slate-500">管理账号连接、业务目标、检测阈值和指标口径。</p>
      </div>

      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
        <p className="text-sm font-medium text-emerald-400">只读安全模式</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">当前连接只用于读取和检测。外部平台写入已禁用，审批与执行模块不在一期前台开放。</p>
      </div>

      <div className="flex max-w-full overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/50 p-1">
        {([
          ["connections", "账号连接"],
          ["targets", "业务目标"],
          ["detection", "检测规则"],
          ["metrics", "指标口径"],
        ] as const).map(([value, label]) => <button key={value} onClick={() => { setTab(value); setMessage(""); setMessageError(false); }} className={`shrink-0 rounded-lg px-4 py-2 text-xs ${tab === value ? "bg-sky-500 text-white" : "text-slate-400 hover:text-slate-200"}`}>{label}</button>)}
      </div>

      {message ? <div className={`rounded-xl border px-4 py-3 text-xs ${messageError ? "border-rose-500/20 bg-rose-500/5 text-rose-400" : "border-emerald-500/20 bg-emerald-500/5 text-emerald-400"}`}>{message}</div> : null}

      {tab === "connections" ? <><Section title="Provider 连接">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {connections.map((connection) => (
            <div key={String(connection.id)} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="flex items-center justify-between">
                <p className="font-semibold text-slate-100">{String(connection.provider)}</p>
                <HealthStatusBadge value={connection.status} compact />
              </div>
              <p className="mt-1 text-[10px] text-slate-500">
                凭据已配置：{String(connection.credential_configured)} · 过期时间 {String(connection.token_expires_at ?? "—")}
              </p>
              <p className="mt-1 text-[10px] text-slate-500">Scopes：{Array.isArray(connection.authorized_scopes) ? (connection.authorized_scopes as string[]).length : 0} 项</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button onClick={() => void validate(String(connection.id))} className="rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-300">
                  验证
                </button>
                <button onClick={() => void discover(String(connection.id))} className="rounded border border-slate-700 px-2 py-1 text-[10px] text-slate-300">
                  发现账号
                </button>
                <button onClick={() => void reauthorize(String(connection.id))} className="rounded border border-amber-700 px-2 py-1 text-[10px] text-amber-300">
                  重新授权
                </button>
              </div>
            </div>
          ))}
          {connections.length === 0 ? (
            <p className="py-4 text-sm text-slate-500">
              暂无连接。运行 <code className="text-sky-400">make seed-social-demo</code> 生成演示连接。
            </p>
          ) : null}
        </div>
      </Section>

      {discovered ? (
        <Section title={`发现账号（${String(discovered.count)}）— 选择后链接`}>
          <div className="space-y-2">
            {((discovered.discovered as Array<Record<string, unknown>>) ?? []).map((account) => (
              <label key={String(account.external_account_id)} className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                <input
                  type="checkbox"
                  checked={selectedAccounts.includes(String(account.external_account_id))}
                  onChange={(event) =>
                    setSelectedAccounts((prev) =>
                      event.target.checked
                        ? [...prev, String(account.external_account_id)]
                        : prev.filter((item) => item !== String(account.external_account_id)),
                    )
                  }
                />
                <div>
                  <p className="text-sm text-slate-200">@{String(account.username)}</p>
                  <p className="text-[10px] text-slate-500">
                    {String(account.platform)} · {String(account.account_type)} · {String(account.external_account_id)}
                  </p>
                </div>
              </label>
            ))}
            <button onClick={() => void link(String(discovered.connection_id))} className="rounded-lg border border-sky-700 px-3 py-1.5 text-xs text-sky-300">
              链接选中账号
            </button>
          </div>
        </Section>
      ) : null}

      <Section title="能力矩阵（Capability Registry）">
        <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-xs">
          <thead className="text-slate-500">
            <tr>
              <th className="py-2">Provider</th>
              <th>平台</th>
              <th>能力</th>
              <th>默认支持</th>
              <th>版本</th>
            </tr>
          </thead>
          <tbody>
            {capabilities.slice(0, 40).map((capability) => (
              <tr key={String(capability.id)} className="border-t border-slate-800 text-slate-400">
                <td className="py-1.5">{String(capability.provider)}</td>
                <td>{String(capability.platform)}</td>
                <td>{String(capability.capability_key)}</td>
                <td>{String(capability.default_supported)}</td>
                <td>{String(capability.provider_version)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </Section>
      </> : null}

      {tab === "targets" ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><h2 className="text-sm font-semibold text-slate-200">业务目标</h2><p className="mt-1 text-xs text-slate-500">用于复盘判断和风险提示，不会触发外部平台操作。</p></div><span className="text-[10px] text-slate-600">工作区：{scope.workspaceId}</span></div>
          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {[
              ["target_roas", "目标 ROAS", "平台归因目标"],
              ["break_even_roas", "盈亏平衡 ROAS", "低于该值需要关注"],
              ["target_cpa", "目标 CPA", "平台获客成本目标"],
              ["target_aov", "目标客单价", "第一方订单口径"],
              ["max_daily_spend", "每日花费上限", "所有广告平台合计"],
              ["max_campaign_daily_spend", "单 Campaign 日上限", "仅用于提醒"],
              ["refund_rate_warning", "退款率提醒值", "输入小数，例如 0.1"],
            ].map(([key, label, hint]) => <label key={key} className="rounded-xl border border-slate-800 bg-slate-950/30 p-4"><span className="text-xs font-medium text-slate-300">{label}</span><input type="number" step="0.01" value={targets[key] ?? ""} onChange={(event) => setTargets((previous) => ({ ...previous, [key]: event.target.value }))} className="mt-3 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-sky-500" /><span className="mt-2 block text-[10px] text-slate-600">{hint}</span></label>)}
          </div>
          <div className="mt-5 flex justify-end"><button disabled={saving} onClick={() => void saveTargets()} className="rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">{saving ? "保存中…" : "保存业务目标"}</button></div>
        </section>
      ) : null}

      {tab === "detection" ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6">
          <div><h2 className="text-sm font-semibold text-slate-200">账号检测规则</h2><p className="mt-1 text-xs text-slate-500">调整后用于账号检测和异常排序；未知状态仍不会按正常处理。</p></div>
          <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
            {[
              ["sync_delay_minutes", "同步延迟提醒", "分钟", "超过后显示需观察"],
              ["sync_stale_minutes", "数据过期提醒", "分钟", "超过后阻止确定性经营结论"],
              ["content_inactive_days", "内容停更提醒", "天", "超过后提示检查发布节奏"],
            ].map(([key, label, unit, hint]) => <label key={key} className="rounded-xl border border-slate-800 bg-slate-950/30 p-4"><span className="text-xs font-medium text-slate-300">{label}</span><div className="mt-3 flex items-center gap-2"><input type="number" min="1" value={detectionRules[key] ?? 0} onChange={(event) => setDetectionRules((previous) => ({ ...previous, [key]: Number(event.target.value) }))} className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-sky-500" /><span className="text-xs text-slate-500">{unit}</span></div><span className="mt-2 block text-[10px] text-slate-600">{hint}</span></label>)}
          </div>
          <div className="mt-5 flex justify-end"><button disabled={saving} onClick={() => void saveDetectionRules()} className="rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">{saving ? "保存中…" : "保存检测规则"}</button></div>
        </section>
      ) : null}

      {tab === "metrics" ? (
        <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60">
          <div className="border-b border-slate-800 px-5 py-4"><h2 className="text-sm font-semibold text-slate-200">指标口径</h2><p className="mt-1 text-xs text-slate-500">明确指标来自第一方还是平台报告，避免把不同口径混为一谈。</p></div>
          <div className="overflow-x-auto"><table className="w-full min-w-[880px] text-left text-xs"><thead className="bg-slate-950/30 text-slate-500"><tr><th className="px-5 py-3">指标</th><th>业务定义</th><th>来源</th><th>计量基础</th><th>新鲜度目标</th><th>负责人</th></tr></thead><tbody className="divide-y divide-slate-800">{metricDefinitions.map((metric) => <tr key={String(metric.metric_key)} className="text-slate-400"><td className="px-5 py-4"><p className="font-medium text-slate-200">{String(metric.display_name)}</p><p className="mt-1 text-[10px] text-slate-600">{String(metric.metric_key)}</p></td><td className="max-w-sm pr-6 leading-relaxed">{String(metric.business_definition)}</td><td>{String(metric.source)}</td><td>{String(metric.measurement_basis)}</td><td>{metric.freshness_sla_minutes == null ? "未配置" : `${String(metric.freshness_sla_minutes)} 分钟`}</td><td>{String(metric.owner ?? "—")}</td></tr>)}</tbody></table></div>
        </section>
      ) : null}
    </div>
  );
}
