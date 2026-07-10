"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";
import { formatPrice } from "@/lib/format";
import type { TradeSide } from "@/lib/types";

export function TradeBar() {
  const { selectedTicker, livePrice, trade } = useStore();
  const [quantity, setQuantity] = useState("");
  const [busy, setBusy] = useState<TradeSide | null>(null);
  const [feedback, setFeedback] = useState<{
    kind: "ok" | "error";
    text: string;
  } | null>(null);

  // The field follows the selected chart ticker until the user types their own
  // symbol (override); no effect needed — the value is derived during render.
  const [tickerOverride, setTickerOverride] = useState<string | null>(null);
  const ticker = tickerOverride ?? selectedTicker ?? "";

  const symbol = ticker.trim().toUpperCase();
  const qty = Number(quantity);
  const price = symbol ? livePrice(symbol) : null;
  const estCost = price != null && qty > 0 ? price * qty : null;
  const valid = symbol.length > 0 && qty > 0;

  const submit = async (side: TradeSide) => {
    if (!valid) return;
    setBusy(side);
    setFeedback(null);
    try {
      await trade(symbol, qty, side);
      setFeedback({
        kind: "ok",
        text: `${side === "buy" ? "Bought" : "Sold"} ${qty} ${symbol}${
          price != null ? ` @ ${formatPrice(price)}` : ""
        }`,
      });
      setQuantity("");
    } catch (err) {
      setFeedback({
        kind: "error",
        text: err instanceof Error ? err.message : "Trade failed",
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border bg-surface px-4 py-2">
      <span className="text-[10px] uppercase tracking-wider text-text-muted">
        Trade
      </span>
      <input
        value={ticker}
        onChange={(e) => setTickerOverride(e.target.value)}
        placeholder="Ticker"
        maxLength={6}
        className="w-24 rounded border border-border bg-background px-2 py-1 text-sm uppercase text-text-primary outline-none focus:border-blue"
      />
      <input
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        placeholder="Qty"
        type="number"
        min="0"
        step="any"
        className="w-24 rounded border border-border bg-background px-2 py-1 text-sm text-text-primary outline-none focus:border-blue"
      />
      {estCost != null && (
        <span className="font-mono text-xs text-text-muted">
          ≈ {formatPrice(estCost)}
        </span>
      )}
      <button
        onClick={() => submit("buy")}
        disabled={!valid || busy !== null}
        className="rounded bg-purple px-4 py-1 text-sm font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy === "buy" ? "…" : "Buy"}
      </button>
      <button
        onClick={() => submit("sell")}
        disabled={!valid || busy !== null}
        className="rounded bg-purple px-4 py-1 text-sm font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy === "sell" ? "…" : "Sell"}
      </button>
      {feedback && (
        <span
          className={`font-mono text-xs ${
            feedback.kind === "ok" ? "text-up" : "text-down"
          }`}
        >
          {feedback.text}
        </span>
      )}
    </div>
  );
}
