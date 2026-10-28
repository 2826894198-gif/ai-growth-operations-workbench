export function TargetIndicator({ current, target }: { current?: number | null; target?: number | null }) {
  if (current == null || target == null) return null;
  const pct = ((current - target) / target) * 100;
  return (
    <span className={`text-xs ${pct <= 0 ? "text-emerald-400" : "text-amber-400"}`}>
      当前 {current.toFixed(2)} / 目标 {target.toFixed(2)}（{pct > 0 ? "+" : ""}
      {pct.toFixed(1)}%）
    </span>
  );
}
