"use client";

import { ResponsiveContainer, Treemap } from "recharts";
import { useStore } from "@/lib/store";
import { formatPercent } from "@/lib/format";
import { Panel } from "./Panel";

interface Node {
  name: string;
  size: number;
  pnlPct: number;
  [key: string]: string | number;
}

/** Emerald for gains, rose for losses; intensity scales with |pnl%| up to ~5%. */
function pnlFill(pnlPct: number): string {
  const t = Math.min(Math.abs(pnlPct) / 5, 1);
  const base = 0.15;
  const alpha = base + t * 0.55;
  const rgb = pnlPct >= 0 ? "16, 185, 129" : "244, 63, 94";
  return `rgba(${rgb}, ${alpha})`;
}

interface CellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pnlPct?: number;
}

function Cell({ x = 0, y = 0, width = 0, height = 0, name, pnlPct }: CellProps) {
  if (width <= 0 || height <= 0) return null;
  const showLabel = width > 44 && height > 28;
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        rx={8}
        fill={pnlFill(pnlPct ?? 0)}
        stroke="#0f172a"
        strokeWidth={3}
      />
      {showLabel && name && (
        <>
          <text
            x={x + 10}
            y={y + 20}
            fill="#f1f5f9"
            fontSize={13}
            fontWeight={700}
          >
            {name}
          </text>
          <text
            x={x + 10}
            y={y + 36}
            fill="#f1f5f9"
            fontSize={11}
            opacity={0.85}
          >
            {formatPercent(pnlPct ?? 0)}
          </text>
        </>
      )}
    </g>
  );
}

export function PortfolioHeatmap() {
  const { portfolio, livePrice } = useStore();

  const nodes: Node[] = (portfolio?.positions ?? [])
    .map((p) => {
      const price = livePrice(p.ticker) ?? p.current_price;
      const size = Math.max(price * p.quantity, 0);
      const pnlPct = p.avg_cost > 0 ? (price / p.avg_cost - 1) * 100 : 0;
      return { name: p.ticker, size, pnlPct };
    })
    .filter((n) => n.size > 0);

  return (
    <Panel title="Portfolio Heatmap" bodyClassName="p-1">
      {nodes.length > 0 ? (
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={nodes}
            dataKey="size"
            isAnimationActive={false}
            content={<Cell />}
          />
        </ResponsiveContainer>
      ) : (
        <div className="flex h-full items-center justify-center text-xs text-text-muted">
          No positions yet
        </div>
      )}
    </Panel>
  );
}
