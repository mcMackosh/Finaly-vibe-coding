"use client";

import { useEffect, useRef, useState } from "react";
import { useStore } from "@/lib/store";
import { formatPercent, formatPrice } from "@/lib/format";
import { Panel } from "./Panel";
import { Sparkline } from "./Sparkline";
import type { PriceTick } from "@/lib/types";
import type { PricePoint } from "@/lib/store";

/** A compact ticker row for the SaaS watchlist. */
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
  const isUp = (changePct ?? 0) >= 0;

  return (
    <div
      role="row"
      onClick={onSelect}
      className={`group flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 transition-colors hover:bg-surface-raised ${
        selected ? "bg-surface-raised ring-1 ring-accent/40" : ""
      }`}
    >
      {/* Left: ticker + sparkline */}
      <div className="flex items-center gap-3">
        <span className="w-14 font-mono text-sm font-semibold text-text-primary">
          {ticker}
        </span>
        <Sparkline points={history} />
      </div>

      {/* Right: price + change pill */}
      <div className="flex flex-col items-end gap-0.5">
        <span
          ref={priceRef}
          className="price-cell rounded px-1 font-mono text-sm font-medium text-text-primary"
        >
          {formatPrice(price)}
        </span>
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold ${
            isUp
              ? "bg-emerald-500/15 text-emerald-400"
              : "bg-rose-500/15 text-rose-400"
          }`}
        >
          {formatPercent(changePct)}
        </span>
      </div>

      {/* Remove button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        aria-label={`Remove ${ticker}`}
        className="ml-2 hidden text-xs text-text-muted hover:text-rose-400 group-hover:inline"
      >
        ✕
      </button>
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
      title="Markets"
      actions={
        <form onSubmit={handleAdd} className="flex items-center gap-1.5">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ticker"
            maxLength={6}
            className="w-20 rounded-lg border border-border bg-background px-2 py-1 text-xs uppercase text-text-primary outline-none focus:border-accent"
          />
          <button
            type="submit"
            className="flex h-6 w-6 items-center justify-center rounded-lg bg-accent/10 text-xs font-semibold text-accent hover:bg-accent/20"
          >
            +
          </button>
        </form>
      }
      bodyClassName="overflow-y-auto p-1.5"
    >
      {error && (
        <p className="mx-3 mb-1 rounded-lg bg-rose-500/10 px-3 py-1.5 text-xs text-rose-400">{error}</p>
      )}
      <div role="rowgroup" className="space-y-1">
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
          <p className="py-8 text-center text-xs text-text-muted">
            Waiting for price stream…
          </p>
        )}
      </div>
    </Panel>
  );
}
