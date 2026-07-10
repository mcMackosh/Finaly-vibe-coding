"""Shared pydantic models for REST requests/responses and the LLM structured output.

Kept in one module so the API layer and the LLM layer agree on the same shapes
(the chat endpoint auto-executes the trades/watchlist changes the LLM returns).
"""

from typing import Literal

from pydantic import BaseModel, Field

Side = Literal["buy", "sell"]


# --- Portfolio -------------------------------------------------------------

class PositionOut(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    change_percent: float


class PortfolioOut(BaseModel):
    cash_balance: float
    total_value: float
    unrealized_pnl: float = 0.0
    positions: list[PositionOut] = Field(default_factory=list)


class TradeRequest(BaseModel):
    ticker: str
    quantity: float = Field(gt=0)
    side: Side


class SnapshotOut(BaseModel):
    total_value: float
    recorded_at: str


# --- Watchlist -------------------------------------------------------------

class WatchlistItemOut(BaseModel):
    ticker: str
    price: float | None = None
    previous_price: float | None = None
    change_percent: float | None = None


class WatchlistAddRequest(BaseModel):
    ticker: str


# --- Chat / LLM structured output ------------------------------------------

class TradeAction(BaseModel):
    ticker: str
    side: Side
    quantity: float = Field(gt=0)


class WatchlistChange(BaseModel):
    ticker: str
    action: Literal["add", "remove"]


class LlmResponse(BaseModel):
    """Structured output the LLM must return (PLAN.md §9)."""

    message: str
    trades: list[TradeAction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    actions: dict | None = None
    created_at: str


class ChatActionsOut(BaseModel):
    """Executed actions attached to an assistant chat message."""

    trades: list[dict] = Field(default_factory=list)
    watchlist_changes: list[dict] = Field(default_factory=list)
    error: str | None = None


class ChatResponse(BaseModel):
    message: str
    actions: ChatActionsOut
