export function FreshnessBadge({ minutes }: { minutes?: number | null }) {
  if (minutes == null) return <span className="text-xs text-slate-500">未同步</span>;
  const fresh = minutes <= 20;
  return (
    <span className={`text-xs ${fresh ? "text-emerald-400" : minutes <= 60 ? "text-amber-400" : "text-orange-400"}`}>
      {fresh ? "●" : "⚠"} 更新于 {Math.round(minutes)} 分钟前
    </span>
  );
}
