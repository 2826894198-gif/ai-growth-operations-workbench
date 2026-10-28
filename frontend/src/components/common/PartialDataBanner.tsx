export function PartialDataBanner({ sources }: { sources: string[] }) {
  if (sources.length === 0) return null;
  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
      部分数据源不可用：{sources.join("、")}。当前页面显示的是部分数据。
    </div>
  );
}
