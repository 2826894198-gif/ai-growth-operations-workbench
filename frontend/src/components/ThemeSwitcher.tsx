import { useEffect, useState } from "react";

export const THEMES = [
  { id: "deepseek", label: "DeepSeek 蓝" },
  { id: "vercel", label: "Vercel 极简" },
  { id: "linear", label: "Linear 蓝紫" },
  { id: "notion", label: "Notion 纸感" },
  { id: "stripe", label: "Stripe 质感" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

function applyTheme(theme: ThemeId) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("growth_theme", theme);
}

export function ThemeSwitcher() {
  const [theme, setTheme] = useState<ThemeId>("deepseek");

  useEffect(() => {
    const stored = localStorage.getItem("growth_theme") as ThemeId | null;
    const initial = stored && THEMES.some((t) => t.id === stored) ? stored : "deepseek";
    setTheme(initial);
    applyTheme(initial);
  }, []);

  const change = (next: ThemeId) => {
    setTheme(next);
    applyTheme(next);
  };

  return (
    <select
      value={theme}
      onChange={(event) => change(event.target.value as ThemeId)}
      title="主题"
      className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-300"
    >
      {THEMES.map((item) => (
        <option key={item.id} value={item.id}>
          {item.label}
        </option>
      ))}
    </select>
  );
}
