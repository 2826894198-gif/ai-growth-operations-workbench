import { useEffect, useMemo, useState } from "react";

export interface ChartTheme {
  text: string;
  muted: string;
  grid: string;
  border: string;
  series: string[];
}

function cssRgb(token: string, fallback: string) {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  if (!value) return fallback;
  if (value.startsWith("#") || value.startsWith("rgb") || value.startsWith("hsl")) return value;
  const channels = value.split(/\s+/).filter(Boolean).slice(0, 3);
  return channels.length === 3 ? `rgb(${channels.join(", ")})` : fallback;
}

export function useChartTheme(): ChartTheme {
  const [themeVersion, setThemeVersion] = useState(0);

  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => setThemeVersion((value) => value + 1));
    observer.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return useMemo(
    () => ({
      text: cssRgb("--c-slate-100", "#e2e8f0"),
      muted: cssRgb("--c-slate-500", "#94a3b8"),
      grid: cssRgb("--c-slate-800", "#1e293b"),
      border: cssRgb("--c-slate-700", "#334155"),
      series: [
        cssRgb("--c-sky-500", "#38bdf8"),
        cssRgb("--c-emerald-500", "#34d399"),
        cssRgb("--c-amber-500", "#fbbf24"),
        cssRgb("--c-violet-500", "#a78bfa"),
        cssRgb("--c-rose-500", "#fb7185"),
      ],
    }),
    [themeVersion],
  );
}
