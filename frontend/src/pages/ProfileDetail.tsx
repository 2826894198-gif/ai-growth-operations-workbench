import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { PageHeader } from "../components/PageHeader";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";
import type { ProfileDetail as ProfileDetailData } from "../types";

function Row({ label, value }: { label: string; value?: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-800/60 py-2 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="text-right text-slate-200">{value ?? "—"}</span>
    </div>
  );
}

export function ProfileDetail() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<ProfileDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      setProfile(await api.profile(id));
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const runAction = useCallback(
    async (action: () => Promise<unknown>, message: string) => {
      setNotice(null);
      try {
        await action();
        setNotice(message);
        await load();
      } catch (error) {
        setNotice(`操作失败：${(error as Error).message}`);
      }
    },
    [load],
  );

  if (loading) return <Spinner />;
  if (!profile) {
    return (
      <div className="space-y-4">
        <Link to="/" className="text-sm text-sky-300 hover:text-sky-200">
          ← 返回
        </Link>
        <p className="text-slate-400">{notice ?? "未找到该环境。"}</p>
      </div>
    );
  }

  const latestHealth = profile.health_checks[0];

  return (
    <div className="space-y-6">
      <PageHeader
        title={profile.name}
        subtitle={`${profile.profile_type} · ${profile.provider}`}
        actions={
          <div className="flex gap-2">
            <Link
              to="/"
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
            >
              ← 返回
            </Link>
            <button
              onClick={() =>
                void runAction(() => api.healthCheck(profile.id), "健康检查已排队")
              }
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
            >
              健康检查
            </button>
            <button
              onClick={() =>
                void runAction(
                  () =>
                    profile.status === "RUNNING"
                      ? api.closeProfile(profile.id)
                      : api.openProfile(profile.id),
                  profile.status === "RUNNING" ? "浏览器已关闭" : "浏览器已打开",
                )
              }
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
            >
              {profile.status === "RUNNING" ? "关闭" : "打开"}
            </button>
            <button
              onClick={() =>
                void runAction(
                  () => api.createTask(profile.id, "smoke_test"),
                  "冒烟测试已排队",
                )
              }
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
            >
              冒烟测试
            </button>
          </div>
        }
      />

      {notice ? (
        <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-sm text-sky-200">
          {notice}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <Section title="环境信息">
          <Row label="状态" value={<Badge value={profile.status} />} />
          <Row label="健康" value={<Badge value={latestHealth?.status ?? "UNKNOWN"} />} />
          <Row label="类型" value={profile.profile_type} />
          <Row label="AdsPower ID" value={profile.provider_profile_id} />
          <Row label="国家 / 地区 / 城市" value={`${profile.country ?? "—"} / ${profile.region ?? "—"} / ${profile.city ?? "—"}`} />
          <Row label="时区" value={profile.timezone} />
          <Row label="语言" value={profile.language} />
          <Row label="浏览器内核" value={profile.browser_engine} />
          <Row label="平台" value={profile.platform} />
          <Row label="上次打开" value={profile.last_opened_at ? new Date(profile.last_opened_at).toLocaleString() : undefined} />
          <Row label="上次关闭" value={profile.last_closed_at ? new Date(profile.last_closed_at).toLocaleString() : undefined} />
        </Section>

        <Section title="代理状态">
          {profile.proxy ? (
            <>
              <Row label="地址" value={`${profile.proxy.host}:${profile.proxy.port}`} />
              <Row label="类型" value={profile.proxy.proxy_type} />
              <Row label="国家" value={profile.proxy.country} />
              <Row label="状态" value={<Badge value={profile.proxy.status} />} />
              <Row label="最近 IP" value={profile.proxy.last_ip} />
              <Row label="延迟" value={profile.proxy.latency_ms ? `${profile.proxy.latency_ms} ms` : undefined} />
              <Row label="上次检查" value={profile.proxy.last_checked_at ? new Date(profile.proxy.last_checked_at).toLocaleString() : undefined} />
            </>
          ) : (
            <p className="py-4 text-sm text-slate-500">未绑定代理。</p>
          )}
        </Section>

        <Section title="指纹基线">
          {profile.fingerprint_config ? (
            <pre className="max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
              {JSON.stringify(profile.fingerprint_config, null, 2)}
            </pre>
          ) : (
            <p className="py-4 text-sm text-slate-500">
              首次同步/创建时自动生成基线。
            </p>
          )}
        </Section>
      </div>

      <Section title="环境健康">
        {latestHealth ? (
          <div className="space-y-2">
            <Row label="状态" value={<Badge value={latestHealth.status} />} />
            <Row label="公网 IP" value={latestHealth.public_ip} />
            <Row label="国家" value={latestHealth.country} />
            <Row label="时区" value={latestHealth.timezone} />
            <Row label="语言" value={latestHealth.language} />
            <Row label="代理延迟" value={latestHealth.proxy_latency_ms ? `${latestHealth.proxy_latency_ms} ms` : undefined} />
            <Row label="浏览器启动" value={latestHealth.browser_launch_ms ? `${latestHealth.browser_launch_ms} ms` : undefined} />
            <Row label="检查时间" value={new Date(latestHealth.created_at).toLocaleString()} />
          </div>
        ) : (
          <p className="py-4 text-sm text-slate-500">
            还没有健康检查记录，运行一次健康检查以建立基线。
          </p>
        )}
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="任务历史">
          {profile.recent_tasks.length === 0 ? (
            <p className="py-4 text-sm text-slate-500">暂无任务。</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs uppercase text-slate-500">
                  <th className="py-2 pr-2">任务</th>
                  <th className="py-2 pr-2">类型</th>
                  <th className="py-2 pr-2">状态</th>
                  <th className="py-2">创建时间</th>
                </tr>
              </thead>
              <tbody>
                {profile.recent_tasks.map((task) => (
                  <tr key={task.id} className="border-b border-slate-800/60">
                    <td className="py-2 pr-2 text-slate-200">{task.task_name}</td>
                    <td className="py-2 pr-2 text-slate-400">{task.task_type}</td>
                    <td className="py-2 pr-2">
                      <Badge value={task.status} />
                    </td>
                    <td className="py-2 text-slate-400">{new Date(task.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>

        <Section title="错误记录">
          {profile.recent_tasks.filter((t) => t.status === "FAILED" || t.status === "TIMEOUT").length === 0 ? (
            <p className="py-4 text-sm text-slate-500">暂无错误记录。</p>
          ) : (
            <div className="space-y-2">
              {profile.recent_tasks
                .filter((t) => t.status === "FAILED" || t.status === "TIMEOUT")
                .map((task) => (
                  <div key={task.id} className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-3 text-sm">
                    <p className="font-medium text-rose-300">
                      {task.error_code ?? task.status} · {new Date(task.created_at).toLocaleString()}
                    </p>
                    <p className="mt-1 break-words text-slate-400">{task.error_message ?? "—"}</p>
                    {task.log_path ? <p className="mt-1 text-xs text-slate-500">日志：{task.log_path}</p> : null}
                  </div>
                ))}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}
