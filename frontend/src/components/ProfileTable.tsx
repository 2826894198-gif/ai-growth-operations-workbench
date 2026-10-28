import { Link } from "react-router-dom";
import type { BrowserProfile } from "../types";
import { Badge } from "./Badge";

interface ProfileTableProps {
  profiles: BrowserProfile[];
  busy: string | null;
  onHealthCheck: (id: string) => void;
  onOpen: (id: string) => void;
  onClose: (id: string) => void;
  onSmokeTest: (id: string) => void;
}

export function ProfileTable({
  profiles,
  busy,
  onHealthCheck,
  onOpen,
  onClose,
  onSmokeTest,
}: ProfileTableProps) {
  if (profiles.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">暂无浏览器环境。</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-500">
            <th className="px-3 py-2">环境</th>
            <th className="px-3 py-2">类型</th>
            <th className="px-3 py-2">地区</th>
            <th className="px-3 py-2">代理</th>
            <th className="px-3 py-2">健康</th>
            <th className="px-3 py-2">状态</th>
            <th className="px-3 py-2">上次检查</th>
            <th className="px-3 py-2 text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          {profiles.map((profile) => (
            <tr key={profile.id} className="border-b border-slate-800/60">
              <td className="px-3 py-3">
                <Link to={`/profiles/${profile.id}`} className="font-medium text-sky-300 hover:text-sky-200">
                  {profile.name}
                </Link>
              </td>
              <td className="px-3 py-3 text-slate-300">{profile.profile_type}</td>
              <td className="px-3 py-3 text-slate-300">
                {[profile.city, profile.country].filter(Boolean).join(", ") || "—"}
              </td>
              <td className="px-3 py-3 text-slate-300">
                {profile.proxy ? `${profile.proxy.country || "?"} · ${profile.proxy.host}` : "—"}
              </td>
              <td className="px-3 py-3">
                <Badge value={profile.status === "RUNNING" ? "RUNNING" : profile.health ?? "UNKNOWN"} />
              </td>
              <td className="px-3 py-3">
                <Badge value={profile.status} />
              </td>
              <td className="px-3 py-3 text-slate-400">
                {profile.last_health_check_at ? new Date(profile.last_health_check_at).toLocaleString() : "—"}
              </td>
              <td className="px-3 py-3">
                <div className="flex justify-end gap-1.5">
                  <ActionButton
                    label="健康检查"
                    disabled={busy === profile.id}
                    onClick={() => onHealthCheck(profile.id)}
                  />
                  {profile.status === "RUNNING" ? (
                    <ActionButton label="关闭" disabled={busy === profile.id} onClick={() => onClose(profile.id)} />
                  ) : (
                    <ActionButton label="打开" disabled={busy === profile.id} onClick={() => onOpen(profile.id)} />
                  )}
                  <ActionButton label="冒烟测试" disabled={busy === profile.id} onClick={() => onSmokeTest(profile.id)} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:border-slate-500 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {label}
    </button>
  );
}
