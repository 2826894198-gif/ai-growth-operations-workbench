import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { BaseChart } from "./BaseChart";
import { useChartTheme } from "./useChartTheme";

export function ScatterMatrixChart({
  rows,
  xKey,
  yKey,
  xName,
  yName,
  sizeKey,
  visualKey,
  ariaLabel,
  onEvent,
}: {
  rows: Array<Record<string, unknown>>;
  xKey: string;
  yKey: string;
  xName: string;
  yName: string;
  sizeKey?: string;
  visualKey?: string;
  ariaLabel?: string;
  onEvent?: (type: string, params: unknown) => void;
}) {
  const theme = useChartTheme();
  const option = useMemo<EChartsOption>(() => {
    const validRows = rows.filter((row) => Number.isFinite(Number(row[xKey])) && Number.isFinite(Number(row[yKey])));
    const sizeValues = sizeKey ? validRows.map((r) => Number(r[sizeKey] || 0)) : [];
    const maxSize = sizeValues.length ? Math.max(...sizeValues) : 1;
    const visualValues = visualKey ? validRows.map((r) => Number(r[visualKey] || 0)) : [];
    const visualMin = visualValues.length ? Math.min(...visualValues) : 0;
    const visualMax = visualValues.length ? Math.max(...visualValues) : 0;
    const hasVisualRange = Boolean(visualKey && visualValues.length > 1 && visualMax > visualMin);
    return {
      animation: validRows.length <= 120,
      aria: { show: true, decal: { show: true } },
      grid: { left: 64, right: visualKey ? 76 : 24, top: 24, bottom: 48, containLabel: true },
      tooltip: {
        trigger: "item",
        formatter: (params: { data?: { row?: Record<string, unknown>; value?: unknown[] }; name?: string }) => {
          const row = params.data?.row ?? {};
          const value = params.data?.value ?? [];
          return `${params.name || "内容"}<br/>${xName}: ${Number(value[0] ?? row[xKey] ?? 0).toFixed(1)}<br/>${yName}: ${Number(value[1] ?? row[yKey] ?? 0).toFixed(1)}`;
        },
      },
      xAxis: {
        type: "value",
        name: xName,
        nameTextStyle: { color: theme.muted },
        splitLine: { lineStyle: { color: theme.grid, type: "dashed" } },
        axisLine: { lineStyle: { color: theme.border } },
        axisLabel: { color: theme.muted },
      },
      yAxis: {
        type: "value",
        name: yName,
        nameLocation: "middle",
        nameGap: 44,
        nameTextStyle: { color: theme.muted },
        splitLine: { lineStyle: { color: theme.grid, type: "dashed" } },
        axisLine: { lineStyle: { color: theme.border } },
        axisLabel: { color: theme.muted },
      },
      visualMap: hasVisualRange
        ? {
            min: visualMin,
            max: visualMax,
            dimension: 3,
            orient: "vertical",
            right: 0,
            top: 20,
            textStyle: { color: theme.muted },
            inRange: { color: [theme.grid, theme.series[0], theme.series[3], theme.series[2]] },
          }
        : undefined,
      series: [
        {
          type: "scatter",
          data: validRows.map((row, index) => ({
            name: String(row.name || row.caption || row.id || `item ${index + 1}`),
            value: [
              Number(row[xKey]),
              Number(row[yKey]),
              sizeKey ? Number(row[sizeKey] || 0) : 8,
              visualKey ? Number(row[visualKey] || 0) : 0,
            ],
            row,
          })),
          symbolSize: (value: number[]) => (sizeKey ? Math.max(9, Math.sqrt(Math.max(value[2], 0) / maxSize) * 38) : 12),
          itemStyle: { opacity: 0.84, color: theme.series[0] },
        },
      ],
    } as EChartsOption;
  }, [rows, xKey, yKey, xName, yName, sizeKey, visualKey, theme]);

  return <BaseChart option={option} className="h-80 w-full" onEvent={onEvent} ariaLabel={ariaLabel || "内容表现散点图"} />;
}
