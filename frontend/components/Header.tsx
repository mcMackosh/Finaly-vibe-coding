"use client";

import { useStore, type ConnectionStatus } from "@/lib/store";
import { formatCurrency, formatSignedCurrency, pnlColor } from "@/lib/format";

const STATUS_META: Record<
  ConnectionStatus,
  { dot: string; label: string }
> = {
  connecting: { dot: "bg-accent animate-pulse", label: "Connecting…" },
  connected: { dot: "bg-up", label: "Live" },
  reconnecting: { dot: "bg-accent animate-pulse", label: "Reconnecting…" },
  disconnected: { dot: "bg-down", label: "Disconnected" },
};

function StatPill({
  label,
  value,
  valueClass = "text-text-primary",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="text-[10px] font-medium text-text-muted">{label}</span>
      <span className={`text-sm font-bold tabular-nums ${valueClass}`}>{value}</span>
    </div>
  );
}

function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  const { dot, label } = STATUS_META[status];
  return (
    <div className="flex items-center gap-1.5 rounded-full bg-surface-raised px-3 py-1">
      <span className={`inline-block h-2 w-2 rounded-full ${dot}`} />
      <span className="text-xs font-medium text-text-muted">{label}</span>
    </div>
  );
}

export function Header() {
  const { portfolio, connectionStatus } = useStore();

  const totalValue = portfolio?.total_value ?? 0;
  const cash = portfolio?.cash_balance ?? 0;
  const pnl = portfolio?.unrealized_pnl ?? 0;

  return (
    <header className="flex shrink-0 items-center justify-between bg-surface px-6 py-3 shadow-sm">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 shadow-sm">
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M3 14L7 8.5L10.5 12L13 7L17 10"
              stroke="#06b6d4"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div>
          <span className="text-lg font-bold text-text-primary">
            Fin<span className="text-accent">Ally</span>
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-6">
        <StatPill label="Portfolio" value={formatCurrency(totalValue)} valueClass="text-accent" />
        <div className="h-8 w-px bg-border" />
        <StatPill label="Cash" value={formatCurrency(cash)} />
        <div className="h-8 w-px bg-border" />
        <StatPill
          label="P&L"
          value={formatSignedCurrency(pnl)}
          valueClass={pnlColor(pnl)}
        />
        <div className="h-8 w-px bg-border" />
        <ConnectionBadge status={connectionStatus} />
      </div>
    </header>
  );
}
