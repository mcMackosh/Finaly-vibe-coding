"use client";

import { useState } from "react";
import { StoreProvider } from "@/lib/store";
import { Header } from "@/components/Header";
import { Watchlist } from "@/components/Watchlist";
import { MainChart } from "@/components/MainChart";
import { PortfolioHeatmap } from "@/components/PortfolioHeatmap";
import { PortfolioChart } from "@/components/PortfolioChart";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { ChatPanel } from "@/components/ChatPanel";

function Workstation() {
  const [chatOpen, setChatOpen] = useState(true);

  return (
    <div className="flex h-screen flex-col bg-background text-text-primary">
      <Header />

      <div className="flex min-h-0 flex-1">
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 overflow-auto p-2 lg:grid-cols-[280px_1fr] lg:overflow-hidden">
            <div className="min-h-0 lg:overflow-hidden">
              <Watchlist />
            </div>

            <div className="grid min-h-0 grid-rows-[minmax(220px,2fr)_minmax(180px,1fr)_minmax(160px,1fr)] gap-2">
              <MainChart />
              <div className="grid min-h-0 grid-cols-1 gap-2 md:grid-cols-2">
                <PortfolioHeatmap />
                <PortfolioChart />
              </div>
              <PositionsTable />
            </div>
          </div>

          <TradeBar />
        </main>

        <ChatPanel open={chatOpen} onToggle={() => setChatOpen((v) => !v)} />
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <StoreProvider>
      <Workstation />
    </StoreProvider>
  );
}
