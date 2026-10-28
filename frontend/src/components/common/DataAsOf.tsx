export function DataAsOf({ value }: { value?: string }) {
  if (!value) return null;
  return <span className="text-xs text-slate-500">更新于 {new Date(value).toLocaleString()}</span>;
}
