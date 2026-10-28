import { useEffect, useRef } from "react";
import * as echarts from "echarts";

export function TrendChart({ data, metric }: { data: Array<Record<string, unknown>>; metric: "spend" | "net_revenue" | "blended_roas" }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chart.setOption({
      grid: { left: 60, right: 20, top: 20, bottom: 30 },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: data.map((d) => String(d.date)), axisLine: { lineStyle: { color: "#334155" } } },
      yAxis: { type: "value", splitLine: { lineStyle: { color: "#1e293b" } } },
      series: [
        {
          name: metric,
          type: "line",
          smooth: true,
          data: data.map((d) => d[metric] as number),
          lineStyle: { color: "#38bdf8" },
          itemStyle: { color: "#38bdf8" },
          areaStyle: { opacity: 0.08 },
        },
      ],
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [data, metric]);
  return <div ref={ref} className="h-64 w-full" />;
}
