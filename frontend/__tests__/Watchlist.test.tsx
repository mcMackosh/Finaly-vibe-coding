import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Watchlist } from "@/components/Watchlist";
import type { PriceTick, WatchlistItem } from "@/lib/types";

const { storeRef } = vi.hoisted(() => ({
  storeRef: { current: null as unknown as Record<string, unknown> },
}));

vi.mock("@/lib/store", () => ({ useStore: () => storeRef.current }));

// Keep the flash class on the element by making rAF a no-op (it normally
// schedules removal on the next frame).
beforeEach(() => {
  vi.stubGlobal("requestAnimationFrame", () => 0);
  vi.stubGlobal("cancelAnimationFrame", () => {});
});

function tick(ticker: string, direction: "up" | "down"): PriceTick {
  return {
    ticker,
    price: 190,
    previous_price: 189,
    change: 1,
    change_percent: 0.53,
    direction,
    timestamp: new Date().toISOString(),
  };
}

function makeStore(overrides: Partial<Record<string, unknown>> = {}) {
  const watchlist: WatchlistItem[] = [
    { ticker: "AAPL", price: 190, previous_price: 189, change_percent: 0.53 },
  ];
  return {
    watchlist,
    prices: { AAPL: tick("AAPL", "up") },
    priceHistory: {},
    selectedTicker: "AAPL",
    setSelectedTicker: vi.fn(),
    addTicker: vi.fn().mockResolvedValue(undefined),
    removeTicker: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("Watchlist", () => {
  beforeEach(() => {
    storeRef.current = makeStore();
  });

  it("applies the up-flash class when a tick arrives", () => {
    render(<Watchlist />);
    const priceCell = screen.getByText("$190.00");
    expect(priceCell.className).toContain("flash-up");
  });

  it("applies the down-flash class on a downtick", () => {
    storeRef.current = makeStore({ prices: { AAPL: tick("AAPL", "down") } });
    render(<Watchlist />);
    expect(screen.getByText("$190.00").className).toContain("flash-down");
  });

  it("removes a ticker when its ✕ is clicked", async () => {
    const removeTicker = vi.fn().mockResolvedValue(undefined);
    storeRef.current = makeStore({ removeTicker });
    render(<Watchlist />);
    await userEvent.click(screen.getByRole("button", { name: /remove aapl/i }));
    expect(removeTicker).toHaveBeenCalledWith("AAPL");
  });

  it("adds a ticker via the add form", async () => {
    const addTicker = vi.fn().mockResolvedValue(undefined);
    storeRef.current = makeStore({ addTicker });
    render(<Watchlist />);
    await userEvent.type(screen.getByPlaceholderText("Ticker"), "pypl");
    await userEvent.click(screen.getByRole("button", { name: "+" }));
    expect(addTicker).toHaveBeenCalledWith("PYPL");
  });
});
