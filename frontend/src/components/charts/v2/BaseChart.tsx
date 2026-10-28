import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

export function BaseChart({
  option,
  className = "h-72 w-full",
  onEvent,
  ariaLabel,
}: {
  option: EChartsOption;
  className?: string;
  onEvent?: (type: string, params: unknown) => void;
  ariaLabel?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chartRef.current = chart;
    const handler = (event: { type: string; params: unknown }) => {
      onEventRef.current?.(event.type, event.params);
    };
    chart.on("click", (params) => handler({ type: "click", params }));
    chart.on("datazoom", (params) => handler({ type: "datazoom", params }));
    chart.on("legendselectchanged", (params) => handler({ type: "legendselectchanged", params }));
    const resize = () => chart.resize();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    observer?.observe(ref.current);
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      observer?.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true });
  }, [option]);

  return <div ref={ref} className={className} role="img" aria-label={ariaLabel || "数据图表"} />;
}
