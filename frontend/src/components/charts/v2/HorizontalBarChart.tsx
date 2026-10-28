import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { BaseChart } from "./BaseChart";
import { useChartTheme } from "./useChartTheme";

export interface HorizontalBarRow {
  label: string;
  value: number;
  id?: string;
}

function compactNumber(value: number) {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}m`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return value.toLocaleString("zh-CN");
}

export function HorizontalBarChart({
  rows,
  color,
  height = "h-80",
  ariaLabel,
  onEvent,
}: {
  rows: HorizontalBarRow[];
  color?: string;
  height?: string;
  ariaLabel?: string;
  onEvent?: (type: string, params: unknown) => void;
}) {
  const theme = useChartTheme();
  const option = useMemo<EChartsOption>(() => {
    const palette = color || theme.series[0];
    return {
      aria: { show: true, decal: { show: true } },
      animation: rows.length <= 20,
      grid: { left: 92, right: 28, top: 12, bottom: 22, containLabel: true },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: Array<{ name?: string; value?: number }>) => {
          const item = params[0];
          return `${item?.name || "内容"}<br/>${Number(item?.value || 0).toLocaleString("zh-CN")}`;
        },
      },
      xAxis: {
        type: "value",
        splitLine: { lineStyle: { color: theme.grid, type: "dashed" } },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: theme.muted, formatter: (value: number) => compactNumber(value) },
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: rows.map((row) => row.label),
        axisLine: { lineStyle: { color: theme.border } },
        axisTick: { show: false },
        axisLabel: { color: theme.text, width: 80, overflow: "truncate" },
      },
      series: [
        {
          type: "bar",
          data: rows.map((row) => row.value),
          barMaxWidth: 18,
          itemStyle: { color: palette, borderRadius: [0, 5, 5, 0] },
          label: { show: true, position: "right", color: theme.muted, formatter: (params: { value?: number }) => compactNumber(Number(params.value || 0)) },
        },
      ],
    } as EChartsOption;
  }, [color, rows, theme]);

  return <BaseChart option={option} className={`w-full ${height}`} onEvent={onEvent} ariaLabel={ariaLabel || "横向排行图表"} />;
}
