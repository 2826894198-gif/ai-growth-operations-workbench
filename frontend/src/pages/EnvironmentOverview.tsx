import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { AlertBanner } from "../components/AlertBanner";
import { PageHeader } from "../components/PageHeader";
import { ProfileTable } from "../components/ProfileTable";
import { Section } from "../components/Section";
import { Spinner } from "../components/Spinner";
import { StatCard } from "../components/StatCard";
import type { Alert, BrowserProfile, EnvironmentOverview } from "../types";

export function EnvironmentOverview() {
  const [overview, setOverview] = useState<EnvironmentOverview | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [profiles, setProfiles] = useState<BrowserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [overviewData, alertData, profileData] = await Promise.all([
        api.overview(),
        api.alerts(),
        api.profiles(),
      ]);
      setOverview(overviewData);
      setAlerts(alertData);
      setProfiles(profileData);
    } catch (error) {
      setNotice(`加载失败：${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runAction = useCallback(
    async (id: string, action: () => Promise<unknown>, message: string) => {
      setBusy(id);
      setNotice(null);
      try {
        await action();
        setNotice(message);
        await load();
      } catch (error) {
        setNotice(`操作失败：${(error as Error).message}`);
      } finally {
        setBusy(null);
      }
    },
    [load],
  );

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="美国运营环境"
        subtitle="AdsPower 浏览器环境 · 浏览器 Worker · 环境健康"
        actions={
          <div className="flex gap-2">
            <Link
              to="/rule-console"
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
            >
              规则引擎
            </Link>
            <Link
              to="/data-health"
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
            >
              数据健康
            </Link>
            <button
              onClick={() => void load()}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
            >
              刷新
            </button>
          </div>
        }
      />

      {notice ? (
        <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-sm text-sky-200">
          {notice}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        <StatCard label="环境总数" value={overview?.total_profiles ?? 0} />
        <StatCard label="健康" value={overview?.healthy_profiles ?? 0} tone="good" />
        <StatCard label="不健康" value={overview?.unhealthy_profiles ?? 0} tone="bad" />
        <StatCard label="运行中" value={overview?.running_browsers ?? 0} />
        <StatCard label="排队任务" value={overview?.queued_tasks ?? 0} tone="warn" />
        <StatCard label="失败任务" value={overview?.failed_tasks ?? 0} tone="bad" />
      </div>

      <AlertBanner alerts={alerts} />

      <Section title="浏览器环境">
        <ProfileTable
          profiles={profiles}
          busy={busy}
          onHealthCheck={(id) =>
            void runAction(id, () => api.healthCheck(id), "健康检查已排队")
          }
          onOpen={(id) => void runAction(id, () => api.openProfile(id), "浏览器已打开")}
          onClose={(id) => void runAction(id, () => api.closeProfile(id), "浏览器已关闭")}
          onSmokeTest={(id) =>
            void runAction(id, () => api.createTask(id, "smoke_test"), "冒烟测试已排队")
          }
        />
      </Section>
    </div>
  );
}
