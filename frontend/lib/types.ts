/**
 * Wire types shared with the FastAPI backend.
 * Mirrors PLAN.md §7/§8 and backend/app/market_data/models.py.
 */

export type Direction = "up" | "down" | "flat";
export type TradeSide = "buy" | "sell";

/** One price update pushed over SSE at `/api/stream/prices`. */
export interface PriceTick {
  ticker: string;
  price: number;
  previous_price: number;
  change: number;
  change_percent: number;
  direction: Direction;
  timestamp: string;
}

/** A watchlist row from `GET /api/watchlist` (ticker plus latest cached price). */
export interface WatchlistItem {
  ticker: string;
  price: number | null;
  previous_price: number | null;
  change_percent: number | null;
}

/** One holding from `GET /api/portfolio`. */
export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  change_percent: number;
}

/** Full portfolio snapshot from `GET /api/portfolio`. */
export interface Portfolio {
  cash_balance: number;
  total_value: number;
  unrealized_pnl: number;
  positions: Position[];
}

/** One point on the portfolio-value line chart (`GET /api/portfolio/history`). */
export interface PortfolioHistoryPoint {
  total_value: number;
  recorded_at: string;
}

/** A trade the LLM (or a manual submit) executed, echoed back for confirmation. */
export interface ExecutedTrade {
  ticker: string;
  side: TradeSide;
  quantity: number;
  price: number;
}

export interface WatchlistChange {
  ticker: string;
  action: "add" | "remove";
}

/** A persisted chat turn from `GET /api/chat/history`. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions: ChatActions | null;
  created_at: string;
}

/** Structured actions attached to an assistant turn. */
export interface ChatActions {
  trades?: ExecutedTrade[];
  watchlist_changes?: WatchlistChange[];
  error?: string;
}

/** Response body from `POST /api/chat`. */
export interface ChatResponse {
  message: string;
  actions: ChatActions | null;
}
