"use client";

/**
 * Central client-side store for FinAlly. Owns the live SSE price stream plus
 * REST-backed portfolio/watchlist/chat state, and exposes mutations. One
 * provider at the app root; components read via `useStore()`.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  PRICES_STREAM_URL,
  addToWatchlist,
  executeTrade,
  fetchChatHistory,
  fetchPortfolio,
  fetchPortfolioHistory,
  fetchWatchlist,
  removeFromWatchlist,
  sendChatMessage,
} from "./api";
import type {
  ChatMessage,
  Portfolio,
  PortfolioHistoryPoint,
  PriceTick,
  TradeSide,
  WatchlistItem,
} from "./types";

export type ConnectionStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";

export interface PricePoint {
  t: number;
  price: number;
}

/** How many accumulated points to keep per ticker for sparklines / main chart. */
const MAX_HISTORY = 300;

interface Store {
  prices: Record<string, PriceTick>;
  priceHistory: Record<string, PricePoint[]>;
  connectionStatus: ConnectionStatus;
  watchlist: WatchlistItem[];
  portfolio: Portfolio | null;
  portfolioHistory: PortfolioHistoryPoint[];
  chatMessages: ChatMessage[];
  selectedTicker: string | null;
  setSelectedTicker: (ticker: string) => void;
  /** Latest live price for a ticker (SSE first, then last known REST value). */
  livePrice: (ticker: string) => number | null;
  addTicker: (ticker: string) => Promise<void>;
  removeTicker: (ticker: string) => Promise<void>;
  trade: (ticker: string, quantity: number, side: TradeSide) => Promise<void>;
  sendChat: (message: string) => Promise<void>;
  chatPending: boolean;
}

const StoreContext = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [prices, setPrices] = useState<Record<string, PriceTick>>({});
  const [priceHistory, setPriceHistory] = useState<Record<string, PricePoint[]>>(
    {},
  );
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [portfolioHistory, setPortfolioHistory] = useState<
    PortfolioHistoryPoint[]
  >([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [chatPending, setChatPending] = useState(false);

  // --- Live price stream (SSE) ---
  useEffect(() => {
    const es = new EventSource(PRICES_STREAM_URL);

    es.onopen = () => setConnectionStatus("connected");
    es.onerror = () => {
      // EventSource reconnects on its own; reflect which phase we're in.
      setConnectionStatus(
        es.readyState === EventSource.CONNECTING ? "reconnecting" : "disconnected",
      );
    };
    es.onmessage = (event) => {
      const tick: PriceTick = JSON.parse(event.data);
      setPrices((prev) => ({ ...prev, [tick.ticker]: tick }));
      setPriceHistory((prev) => {
        const point = { t: Date.parse(tick.timestamp), price: tick.price };
        const existing = prev[tick.ticker] ?? [];
        const next = [...existing, point];
        if (next.length > MAX_HISTORY) next.shift();
        return { ...prev, [tick.ticker]: next };
      });
    };

    return () => es.close();
  }, []);

  // --- Initial REST load (resilient: backend may not be up yet in dev) ---
  const loadWatchlist = useCallback(async () => {
    const data = await fetchWatchlist().catch(() => null);
    if (data) {
      setWatchlist(data);
      setSelectedTicker((cur) => cur ?? data[0]?.ticker ?? null);
    }
  }, []);

  const loadPortfolio = useCallback(async () => {
    const data = await fetchPortfolio().catch(() => null);
    if (data) setPortfolio(data);
  }, []);

  const loadHistory = useCallback(async () => {
    const data = await fetchPortfolioHistory().catch(() => null);
    if (data) setPortfolioHistory(data);
  }, []);

  const loadChat = useCallback(async () => {
    const data = await fetchChatHistory().catch(() => null);
    if (data) setChatMessages(data);
  }, []);

  // Initial one-shot fetch of the REST-backed state. The loaders only setState
  // after their fetch resolves (asynchronously), which the set-state-in-effect
  // rule can't see through — this is a legitimate fetch-on-mount effect.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadWatchlist();
    loadPortfolio();
    loadHistory();
    loadChat();
  }, [loadWatchlist, loadPortfolio, loadHistory, loadChat]);

  const livePrice = useCallback(
    (ticker: string): number | null => {
      const tick = prices[ticker];
      if (tick) return tick.price;
      const item = watchlist.find((w) => w.ticker === ticker);
      return item?.price ?? null;
    },
    [prices, watchlist],
  );

  const addTicker = useCallback(
    async (ticker: string) => {
      await addToWatchlist(ticker);
      await loadWatchlist();
    },
    [loadWatchlist],
  );

  const removeTicker = useCallback(
    async (ticker: string) => {
      await removeFromWatchlist(ticker);
      await loadWatchlist();
    },
    [loadWatchlist],
  );

  const trade = useCallback(
    async (ticker: string, quantity: number, side: TradeSide) => {
      const updated = await executeTrade(ticker, quantity, side);
      setPortfolio(updated);
      await loadHistory();
    },
    [loadHistory],
  );

  const sendChat = useCallback(
    async (message: string) => {
      const optimistic: ChatMessage = {
        id: `local-${Date.now()}`,
        role: "user",
        content: message,
        actions: null,
        created_at: new Date().toISOString(),
      };
      setChatMessages((prev) => [...prev, optimistic]);
      setChatPending(true);
      try {
        const res = await sendChatMessage(message);
        setChatMessages((prev) => [
          ...prev,
          {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: res.message,
            actions: res.actions,
            created_at: new Date().toISOString(),
          },
        ]);
        // The assistant may have traded or changed the watchlist.
        await Promise.all([loadPortfolio(), loadHistory(), loadWatchlist()]);
      } finally {
        setChatPending(false);
      }
    },
    [loadPortfolio, loadHistory, loadWatchlist],
  );

  const value: Store = {
    prices,
    priceHistory,
    connectionStatus,
    watchlist,
    portfolio,
    portfolioHistory,
    chatMessages,
    selectedTicker,
    setSelectedTicker,
    livePrice,
    addTicker,
    removeTicker,
    trade,
    sendChat,
    chatPending,
  };

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): Store {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore must be used within StoreProvider");
  return ctx;
}
