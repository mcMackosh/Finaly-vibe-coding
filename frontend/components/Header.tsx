"use client";

import { useStore, type ConnectionStatus } from "@/lib/store";
import { formatCurrency, formatSignedCurrency, pnlColor } from "@/lib/format";

const STATUS_META: Record<
  ConnectionStatus,
  { color: string; label: string }
> = {
  connecting: { color: "bg-accent", label: "Connecting to price stream…" },
  connected: { color: "bg-up", label: "Live — connected to price stream" },
  reconnecting: { color: "bg-accent", label: "Reconnecting to price stream…" },
  disconnected: { color: "bg-down", label: "Disconnected from price stream" },
};

function ConnectionDot({ status }: { status: ConnectionStatus }) {
  const meta = STATUS_META[status];
  const pulse = status === "connecting" || status === "reconnecting";
  return (
    <div className="group relative flex items-center gap-2">
      <span
        className={`inline-block h-2.5 w-2.5 rounded-full ${meta.color} ${
          pulse ? "animate-pulse" : ""
        }`}
      />
      <span className="text-xs text-text-muted">{status}</span>
      <span className="pointer-events-none absolute right-0 top-full z-20 mt-1 hidden whitespace-nowrap rounded border border-border bg-surface-raised px-2 py-1 text-xs text-text-primary shadow-lg group-hover:block">
        {meta.label}
      </span>
    </div>
  );
}

function Stat({
  label,
  value,
  valueClass = "text-text-primary",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex flex-col items-end">
      <span className="text-[10px] uppercase tracking-wider text-text-muted">
        {label}
      </span>
      <span className={`font-mono text-sm font-semibold tabular-nums ${valueClass}`}>
        {value}
      </span>
    </div>
  );
}

export function Header() {
  const { portfolio, connectionStatus } = useStore();

  const totalValue = portfolio?.total_value ?? 0;
  const cash = portfolio?.cash_balance ?? 0;
  const pnl = portfolio?.unrealized_pnl ?? 0;

  return (
    <header className="flex shrink-0 items-center justify-between border-b border-border bg-surface px-4 py-2.5">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-lg font-bold tracking-tight text-text-primary">
          Fin<span className="text-accent">Ally</span>
        </span>
        <span className="hidden text-xs text-text-muted sm:inline">
          AI Trading Workstation
        </span>
      </div>

      <div className="flex items-center gap-6">
        <Stat label="Portfolio Value" value={formatCurrency(totalValue)} />
        <Stat label="Cash" value={formatCurrency(cash)} />
        <Stat
          label="Unrealized P&L"
          value={formatSignedCurrency(pnl)}
          valueClass={pnlColor(pnl)}
        />
        <ConnectionDot status={connectionStatus} />
      </div>
    </header>
  );
}
