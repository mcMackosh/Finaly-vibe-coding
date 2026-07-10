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

/** Green for gains, red for losses; intensity scales with |pnl%| up to ~5%. */
function pnlFill(pnlPct: number): string {
  const t = Math.min(Math.abs(pnlPct) / 5, 1);
  const base = 0.12;
  const alpha = base + t * 0.5;
  const rgb = pnlPct >= 0 ? "38, 162, 105" : "229, 72, 77";
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
        fill={pnlFill(pnlPct ?? 0)}
        stroke="#0d1117"
        strokeWidth={2}
      />
      {showLabel && name && (
        <>
          <text
            x={x + 6}
            y={y + 16}
            fill="#e6edf3"
            fontSize={12}
            fontFamily="monospace"
            fontWeight={600}
          >
            {name}
          </text>
          <text
            x={x + 6}
            y={y + 30}
            fill="#e6edf3"
            fontSize={10}
            fontFamily="monospace"
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
