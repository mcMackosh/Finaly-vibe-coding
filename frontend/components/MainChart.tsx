"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useStore } from "@/lib/store";
import { formatPercent, formatPrice, pnlColor } from "@/lib/format";
import { Panel } from "./Panel";

export function MainChart() {
  const { selectedTicker, priceHistory, prices } = useStore();

  const ticker = selectedTicker;
  const points = ticker ? priceHistory[ticker] ?? [] : [];
  const tick = ticker ? prices[ticker] : undefined;

  const data = points.map((p) => ({
    time: new Date(p.t).toLocaleTimeString(),
    price: p.price,
  }));

  const rising = (tick?.change ?? 0) >= 0;
  const stroke = rising ? "#10b981" : "#f43f5e";

  return (
    <Panel
      title="Chart"
      actions={
        ticker ? (
          <div className="flex items-baseline gap-3">
            <span className="font-mono text-sm font-semibold text-accent">
              {ticker}
            </span>
            <span className="font-mono text-sm tabular-nums text-text-primary">
              {formatPrice(tick?.price)}
            </span>
            <span
              className={`font-mono text-xs tabular-nums ${pnlColor(
                tick?.change_percent ?? 0,
              )}`}
            >
              {formatPercent(tick?.change_percent)}
            </span>
          </div>
        ) : null
      }
      bodyClassName="p-2"
    >
      {ticker && data.length >= 2 ? (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="mainFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="time"
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              minTickGap={48}
              stroke="#334155"
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              width={56}
              stroke="#334155"
              tickFormatter={(v: number) => v.toFixed(2)}
            />
            <Tooltip
              contentStyle={{
                background: "#2d3a4f",
                border: "1px solid #334155",
                borderRadius: 6,
                fontSize: 12,
              }}
              labelStyle={{ color: "#94a3b8" }}
              formatter={(v) => [formatPrice(Number(v)), "Price"]}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke={stroke}
              strokeWidth={1.5}
              fill="url(#mainFill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex h-full items-center justify-center text-xs text-text-muted">
          {ticker
            ? "Accumulating price data…"
            : "Select a ticker to view its chart"}
        </div>
      )}
    </Panel>
  );
}
