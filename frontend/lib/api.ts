/**
 * Thin fetch wrapper over the FastAPI `/api/*` routes (PLAN.md §8).
 *
 * In production the frontend is served by FastAPI on the same origin, so the
 * base is empty. For `next dev` against a separately-running backend, set
 * NEXT_PUBLIC_API_BASE (e.g. http://localhost:8000).
 */
import type {
  ChatMessage,
  ChatResponse,
  Portfolio,
  PortfolioHistoryPoint,
  TradeSide,
  WatchlistItem,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

/** Path to the SSE price stream (used directly by EventSource). */
export const PRICES_STREAM_URL = `${API_BASE}/api/stream/prices`;

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, detail?.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export const fetchWatchlist = () => request<WatchlistItem[]>("/api/watchlist");

export const fetchPortfolio = () => request<Portfolio>("/api/portfolio");

export const fetchPortfolioHistory = () =>
  request<PortfolioHistoryPoint[]>("/api/portfolio/history");

export const fetchChatHistory = () => request<ChatMessage[]>("/api/chat/history");

export const addToWatchlist = (ticker: string) =>
  request<WatchlistItem>("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker: ticker.toUpperCase() }),
  });

export const removeFromWatchlist = (ticker: string) =>
  request<void>(`/api/watchlist/${encodeURIComponent(ticker.toUpperCase())}`, {
    method: "DELETE",
  });

export const executeTrade = (
  ticker: string,
  quantity: number,
  side: TradeSide,
) =>
  request<Portfolio>("/api/portfolio/trade", {
    method: "POST",
    body: JSON.stringify({ ticker: ticker.toUpperCase(), quantity, side }),
  });

export const sendChatMessage = (message: string) =>
  request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });

export { ApiError };
