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
              tick={{ fill: "#8b949e", fontSize: 10 }}
              minTickGap={48}
              stroke="#30363d"
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fill: "#8b949e", fontSize: 10 }}
              width={64}
              stroke="#30363d"
              tickFormatter={(v: number) => `$${Math.round(v)}`}
            />
            <Tooltip
              contentStyle={{
                background: "#1c2230",
                border: "1px solid #30363d",
                borderRadius: 6,
                fontSize: 12,
              }}
              labelStyle={{ color: "#8b949e" }}
              formatter={(v) => [formatCurrency(Number(v)), "Value"]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#209dd7"
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
