import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { BaseChart } from "./BaseChart";
import { useChartTheme } from "./useChartTheme";

export function TimeSeriesChart({
  dimensions,
  rows,
  metrics,
  colors,
  stacked,
  dataZoom = true,
  height = "h-64",
  yAxisName,
  ariaLabel,
  onEvent,
}: {
  dimensions: string[];
  rows: Array<Record<string, unknown>>;
  metrics: Array<{ key: string; name: string; color?: string; area?: boolean }>;
  colors?: string[];
  stacked?: boolean;
  dataZoom?: boolean;
  height?: string;
  yAxisName?: string;
  ariaLabel?: string;
  onEvent?: (type: string, params: unknown) => void;
}) {
  const theme = useChartTheme();
  const option = useMemo<EChartsOption>(() => {
    const palette = colors?.length ? colors : theme.series;
    const dimension = dimensions[0] || "date";
    const numberOrNull = (value: unknown) => {
      if (value === null || value === undefined || value === "") return null;
      const number = Number(value);
      return Number.isFinite(number) ? number : null;
    };
    const series = metrics.map((metric, index) => ({
      name: metric.name,
      type: "line" as const,
      smooth: false,
      showSymbol: rows.length <= 14,
      stack: stacked ? "total" : undefined,
      connectNulls: false,
      data: rows.map((row) => numberOrNull(row[metric.key])),
      lineStyle: { color: metric.color || palette[index % palette.length], width: 2 },
      itemStyle: { color: metric.color || palette[index % palette.length] },
      areaStyle: metric.area ? { color: metric.color || palette[index % palette.length], opacity: 0.08 } : undefined,
    }));
    return {
      color: palette,
      animation: rows.length <= 90,
      aria: { show: true, decal: { show: true } },
      grid: { left: 58, right: 20, top: metrics.length > 1 ? 36 : 18, bottom: dataZoom && rows.length > 14 ? 52 : 30, containLabel: true },
      tooltip: { trigger: "axis", axisPointer: { type: "line" } },
      legend: { show: metrics.length > 1, top: 0, textStyle: { color: theme.muted } },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: rows.map((row) => String(row[dimension] ?? "")),
        axisLine: { lineStyle: { color: theme.border } },
        axisTick: { show: false },
        axisLabel: { color: theme.muted, hideOverlap: true },
      },
      yAxis: {
        type: "value",
        name: yAxisName,
        nameLocation: "middle",
        nameGap: 42,
        nameTextStyle: { color: theme.muted },
        splitLine: { lineStyle: { color: theme.grid, type: "dashed" } },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: theme.muted, hideOverlap: true },
      },
      dataZoom: dataZoom && rows.length > 14
        ? [{ type: "inside" }, { type: "slider", height: 16, bottom: 10, borderColor: theme.border, textStyle: { color: theme.muted } }]
        : undefined,
      series,
    } as EChartsOption;
  }, [colors, dataZoom, dimensions, metrics, rows, stacked, theme, yAxisName]);

  return <BaseChart option={option} className={`w-full ${height}`} onEvent={onEvent} ariaLabel={ariaLabel || "时间序列图表"} />;
}
