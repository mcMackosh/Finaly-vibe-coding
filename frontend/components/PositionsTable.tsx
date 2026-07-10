"use client";

import { useStore } from "@/lib/store";
import {
  formatCurrency,
  formatPercent,
  formatPrice,
  formatQuantity,
  formatSignedCurrency,
  pnlColor,
} from "@/lib/format";
import { Panel } from "./Panel";

export function PositionsTable() {
  const { portfolio, livePrice, setSelectedTicker } = useStore();
  const positions = portfolio?.positions ?? [];

  return (
    <Panel title="Positions" bodyClassName="overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-surface text-[10px] text-text-muted">
          <tr>
            <th className="pb-2 pl-4 pr-3 text-left font-medium">Symbol</th>
            <th className="pb-2 px-3 text-right font-medium">Shares</th>
            <th className="pb-2 px-3 text-right font-medium">Avg Cost</th>
            <th className="pb-2 px-3 text-right font-medium">Price</th>
            <th className="pb-2 px-3 text-right font-medium">P&L</th>
            <th className="pb-2 pl-3 pr-4 text-right font-medium">%</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {positions.map((p) => {
            const price = livePrice(p.ticker) ?? p.current_price;
            const pnl = (price - p.avg_cost) * p.quantity;
            const pnlPct = p.avg_cost > 0 ? (price / p.avg_cost - 1) * 100 : 0;
            return (
              <tr
                key={p.ticker}
                onClick={() => setSelectedTicker(p.ticker)}
                className="cursor-pointer rounded-lg transition-colors hover:bg-surface-raised"
              >
                <td className="pl-4 pr-3 py-2 font-semibold text-text-primary">{p.ticker}</td>
                <td className="px-3 py-2 text-right text-text-primary">{formatQuantity(p.quantity)}</td>
                <td className="px-3 py-2 text-right text-text-muted">{formatPrice(p.avg_cost)}</td>
                <td className="px-3 py-2 text-right text-text-primary">{formatPrice(price)}</td>
                <td className={`px-3 py-2 text-right font-medium ${pnlColor(pnl)}`}>
                  {formatSignedCurrency(pnl)}
                </td>
                <td className={`pl-3 pr-4 py-2 text-right font-medium ${pnlColor(pnlPct)}`}>
                  {formatPercent(pnlPct)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {positions.length === 0 && (
        <p className="py-8 text-center text-xs text-text-muted">
          No open positions. Use the trade bar below to buy.
        </p>
      )}
      {portfolio && (
        <div className="border-t border-border/50 px-4 py-2.5 text-right text-xs text-text-muted">
          Available cash: <span className="font-semibold text-text-primary">{formatCurrency(portfolio.cash_balance)}</span>
        </div>
      )}
    </Panel>
  );
}
