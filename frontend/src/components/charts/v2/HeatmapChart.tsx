import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { BaseChart } from "./BaseChart";

export function HeatmapChart({
  data,
  xLabels,
  yLabels,
  unit = "",
}: {
  data: number[][];
  xLabels: string[];
  yLabels: string[];
  unit?: string;
}) {
  const option = useMemo<EChartsOption>(() => {
    const values = data.flat().filter((v) => v !== null && v !== undefined) as number[];
    return {
      tooltip: { position: "top", formatter: (params: { value: number[] }) => `${xLabels[params.value[0]]} × ${yLabels[params.value[1]]}: ${params.value[2]}${unit}` },
      grid: { left: 56, right: 80, top: 12, bottom: 40 },
      xAxis: { type: "category", data: xLabels, axisLabel: { color: "#94a3b8" }, splitArea: { show: true } },
      yAxis: { type: "category", data: yLabels, axisLabel: { color: "#94a3b8" }, splitArea: { show: true } },
      visualMap: {
        min: values.length ? Math.min(...values) : 0,
        max: values.length ? Math.max(...values) : 1,
        calculable: true,
        orient: "horizontal",
        right: 0,
        bottom: 0,
        textStyle: { color: "#94a3b8" },
        inRange: { color: ["#0f172a", "#1d4ed8", "#38bdf8", "#fbbf24"] },
      },
      series: [
        {
          type: "heatmap",
          data: data.map((row, y) => row.map((value, x) => [x, y, value])).flat(),
          label: { show: false },
          emphasis: { itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.4)" } },
        },
      ],
    } as EChartsOption;
  }, [data, xLabels, yLabels]);
  return <BaseChart option={option} className="h-64 w-full" />;
}
