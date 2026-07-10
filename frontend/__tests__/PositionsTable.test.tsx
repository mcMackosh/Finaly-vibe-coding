import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { PositionsTable } from "@/components/PositionsTable";
import type { Portfolio } from "@/lib/types";

const { storeRef } = vi.hoisted(() => ({
  storeRef: { current: null as unknown as Record<string, unknown> },
}));

vi.mock("@/lib/store", () => ({ useStore: () => storeRef.current }));

function makeStore(portfolio: Portfolio | null, live: Record<string, number>) {
  return {
    portfolio,
    livePrice: (t: string) => live[t] ?? null,
    setSelectedTicker: vi.fn(),
  };
}

describe("PositionsTable", () => {
  beforeEach(() => {
    storeRef.current = makeStore(null, {});
  });

  it("shows an empty state with no positions", () => {
    render(<PositionsTable />);
    expect(screen.getByText(/no open positions/i)).toBeInTheDocument();
  });

  it("computes P&L from the live price, not the stale snapshot", () => {
    const portfolio: Portfolio = {
      cash_balance: 5000,
      total_value: 6100,
      unrealized_pnl: 100,
      positions: [
        {
          ticker: "AAPL",
          quantity: 10,
          avg_cost: 100,
          current_price: 100, // stale; live price should win
          unrealized_pnl: 0,
          change_percent: 0,
        },
      ],
    };
    storeRef.current = makeStore(portfolio, { AAPL: 110 });

    render(<PositionsTable />);

    // (110 - 100) * 10 = +$100.00, and +10.00%
    expect(screen.getByText("+$100.00")).toBeInTheDocument();
    expect(screen.getByText("+10.00%")).toBeInTheDocument();
    expect(screen.getByText("Available cash:").parentElement).toHaveTextContent(
      "$5,000.00",
    );
  });
});
