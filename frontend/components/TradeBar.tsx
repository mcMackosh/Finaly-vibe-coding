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
        text: `${side === "buy" ? "Bought" : "Sold"} ${qty} ${symbol}${price != null ? ` @ ${formatPrice(price)}` : ""}`,
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
    <div className="flex flex-wrap items-center gap-3 border-t border-border bg-surface px-6 py-3">
      <span className="text-xs font-semibold text-text-muted">Trade</span>

      <input
        value={ticker}
        onChange={(e) => setTickerOverride(e.target.value)}
        placeholder="Symbol"
        maxLength={6}
        className="w-24 rounded-xl border border-border bg-surface-raised px-3 py-1.5 text-sm uppercase text-text-primary outline-none focus:border-accent"
      />
      <input
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        placeholder="Shares"
        type="number"
        min="0"
        step="any"
        className="w-28 rounded-xl border border-border bg-surface-raised px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
      />
      {estCost != null && (
        <span className="text-sm text-text-muted">
          ≈ <span className="font-semibold text-text-primary">{formatPrice(estCost)}</span>
        </span>
      )}

      <button
        onClick={() => submit("buy")}
        disabled={!valid || busy !== null}
        className="rounded-xl bg-emerald-500 px-5 py-1.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-400 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy === "buy" ? "…" : "Buy"}
      </button>
      <button
        onClick={() => submit("sell")}
        disabled={!valid || busy !== null}
        className="rounded-xl bg-rose-500 px-5 py-1.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-rose-400 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy === "sell" ? "…" : "Sell"}
      </button>

      {feedback && (
        <span className={`text-sm font-medium ${feedback.kind === "ok" ? "text-emerald-400" : "text-rose-400"}`}>
          {feedback.text}
        </span>
      )}
    </div>
  );
}
