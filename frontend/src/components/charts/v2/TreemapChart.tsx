import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { BaseChart } from "./BaseChart";

export function TreemapChart({
  data,
  onEvent,
}: {
  data: Array<{ name: string; value: number; children?: Array<{ name: string; value: number }> }>;
  onEvent?: (type: string, params: unknown) => void;
}) {
  const option = useMemo<EChartsOption>(
    () => ({
      tooltip: { formatter: "{b}: {c}" },
      series: [
        {
          type: "treemap",
          roam: false,
          nodeClick: "zoomToNode",
          data,
          label: { color: "#e2e8f0", fontSize: 12 },
          itemStyle: { borderColor: "#0f172a", borderWidth: 2 },
          levels: [
            { itemStyle: { borderColor: "#1e293b", borderWidth: 3, gapWidth: 4 } },
            { colorSaturation: [0.3, 0.6], itemStyle: { borderWidth: 1, gapWidth: 1 } },
          ],
        },
      ],
    }),
    [data],
  );
  return <BaseChart option={option} className="h-64 w-full" onEvent={onEvent} />;
}
