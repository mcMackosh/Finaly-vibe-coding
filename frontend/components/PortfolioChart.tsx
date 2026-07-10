"use client";

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useStore } from "@/lib/store";
import { formatCurrency } from "@/lib/format";
import { Panel } from "./Panel";

export function PortfolioChart() {
  const { portfolioHistory } = useStore();

  const data = portfolioHistory.map((p) => ({
    time: new Date(p.recorded_at).toLocaleTimeString(),
    value: p.total_value,
  }));

  return (
    <Panel title="Portfolio Value" bodyClassName="p-2">
      {data.length >= 2 ? (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <XAxis
              dataKey="time"
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              minTickGap={48}
              stroke="#334155"
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              width={64}
              stroke="#334155"
              tickFormatter={(v: number) => `$${Math.round(v)}`}
            />
            <Tooltip
              contentStyle={{
                background: "#2d3a4f",
                border: "1px solid #334155",
                borderRadius: 6,
                fontSize: 12,
              }}
              labelStyle={{ color: "#94a3b8" }}
              formatter={(v) => [formatCurrency(Number(v)), "Value"]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#3b82f6"
              strokeWidth={1.5}
              isAnimationActive={false}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex h-full items-center justify-center text-xs text-text-muted">
          Portfolio history builds up as you trade
        </div>
      )}
    </Panel>
  );
}
