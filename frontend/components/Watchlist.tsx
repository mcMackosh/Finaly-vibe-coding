"use client";

import { useEffect, useRef, useState } from "react";
import { useStore } from "@/lib/store";
import { formatPercent, formatPrice, pnlColor } from "@/lib/format";
import { Panel } from "./Panel";
import { Sparkline } from "./Sparkline";
import type { PriceTick } from "@/lib/types";
import type { PricePoint } from "@/lib/store";

/** A single watchlist row; flashes green/red on each incoming tick. */
function WatchlistRow({
  ticker,
  tick,
  history,
  selected,
  onSelect,
  onRemove,
}: {
  ticker: string;
  tick: PriceTick | undefined;
  history: PricePoint[];
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const priceRef = useRef<HTMLSpanElement>(null);
  const lastStamp = useRef<string | null>(null);

  useEffect(() => {
    const el = priceRef.current;
    if (!el || !tick) return;
    // Fire once per new tick, even if the numeric price repeats.
    if (tick.timestamp === lastStamp.current) return;
    lastStamp.current = tick.timestamp;
    if (tick.direction === "flat") return;

    const cls = tick.direction === "up" ? "flash-up" : "flash-down";
    el.classList.add(cls);
    const id = requestAnimationFrame(() => el.classList.remove(cls));
    return () => cancelAnimationFrame(id);
  }, [tick]);

  const price = tick?.price ?? null;
  const changePct = tick?.change_percent ?? null;

  return (
    <div
      role="row"
      onClick={onSelect}
      className={`group grid cursor-pointer grid-cols-[1fr_auto_auto] items-center gap-2 border-l-2 px-3 py-1.5 text-sm hover:bg-surface-raised ${
        selected
          ? "border-accent bg-surface-raised"
          : "border-transparent"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="font-mono font-semibold text-text-primary">
          {ticker}
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          aria-label={`Remove ${ticker}`}
          className="hidden text-xs text-text-muted hover:text-down group-hover:inline"
        >
          ✕
        </button>
      </div>

      <Sparkline points={history} />

      <div className="flex flex-col items-end">
        <span
          ref={priceRef}
          className="price-cell px-1 font-mono tabular-nums text-text-primary"
        >
          {formatPrice(price)}
        </span>
        <span className={`font-mono text-xs tabular-nums ${pnlColor(changePct ?? 0)}`}>
          {formatPercent(changePct)}
        </span>
      </div>
    </div>
  );
}

export function Watchlist() {
  const {
    watchlist,
    prices,
    priceHistory,
    selectedTicker,
    setSelectedTicker,
    addTicker,
    removeTicker,
  } = useStore();

  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Fall back to whatever tickers we've seen ticks for if the REST list is empty
  // (e.g. backend watchlist endpoint not up yet in dev).
  const tickers =
    watchlist.length > 0
      ? watchlist.map((w) => w.ticker)
      : Object.keys(prices).sort();

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const symbol = input.trim().toUpperCase();
    if (!symbol) return;
    setError(null);
    try {
      await addTicker(symbol);
      setInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add ticker");
    }
  };

  return (
    <Panel
      title="Watchlist"
      actions={
        <form onSubmit={handleAdd} className="flex items-center gap-1">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Add…"
            maxLength={6}
            className="w-16 rounded border border-border bg-background px-1.5 py-0.5 text-xs uppercase text-text-primary outline-none focus:border-blue"
          />
          <button
            type="submit"
            className="rounded bg-blue px-1.5 py-0.5 text-xs font-semibold text-white hover:opacity-90"
          >
            +
          </button>
        </form>
      }
      bodyClassName="overflow-y-auto"
    >
      {error && (
        <p className="px-3 py-1 text-xs text-down">{error}</p>
      )}
      <div role="rowgroup" className="divide-y divide-border/50">
        {tickers.map((ticker) => (
          <WatchlistRow
            key={ticker}
            ticker={ticker}
            tick={prices[ticker]}
            history={priceHistory[ticker] ?? []}
            selected={ticker === selectedTicker}
            onSelect={() => setSelectedTicker(ticker)}
            onRemove={() => removeTicker(ticker).catch(() => {})}
          />
        ))}
        {tickers.length === 0 && (
          <p className="px-3 py-4 text-center text-xs text-text-muted">
            Waiting for price stream…
          </p>
        )}
      </div>
    </Panel>
  );
}
