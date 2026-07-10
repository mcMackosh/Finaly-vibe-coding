"""Trade execution and portfolio valuation — the shared core behind the trade endpoint
and the LLM chat auto-execution path.

Prices always come from the server's in-memory cache (never the client), so a trade can
only fill at the price the market data layer currently holds.
"""

import sqlite3

from app.database import (
    add_snapshot,
    add_trade,
    delete_position,
    get_position,
    get_profile,
    list_positions,
    update_cash_balance,
    upsert_position,
)
from app.market_data.cache import PriceCache
from app.models import PortfolioOut, PositionOut

# Below this residual quantity a sell is treated as closing the position entirely,
# so floating-point dust never leaves a near-zero row behind.
_CLOSE_EPSILON = 1e-9


class TradeError(Exception):
    """Raised when a trade fails validation (unknown price, insufficient cash/shares)."""


async def _current_price(cache: PriceCache, ticker: str) -> float:
    state = await cache.get(ticker.upper())
    if state is None:
        raise TradeError(f"No live price available for {ticker.upper()}")
    return state.price


async def execute_trade(
    conn: sqlite3.Connection,
    cache: PriceCache,
    ticker: str,
    quantity: float,
    side: str,
) -> dict:
    """Execute a market order at the current cached price. Returns a summary dict.

    Updates positions, cash, the trade log, and records a portfolio snapshot — all on the
    caller's connection so it commits as one transaction. Raises TradeError on validation
    failure (the caller decides whether that becomes an HTTP 400 or a chat error message).
    """
    ticker = ticker.upper()
    if quantity <= 0:
        raise TradeError("Quantity must be positive")

    price = await _current_price(cache, ticker)
    profile = get_profile(conn)
    cash = profile["cash_balance"]
    position = get_position(conn, ticker)

    if side == "buy":
        cost = quantity * price
        if cost > cash:
            raise TradeError(
                f"Insufficient cash: need ${cost:,.2f}, have ${cash:,.2f}"
            )
        if position:
            total_qty = position["quantity"] + quantity
            new_avg_cost = (
                position["quantity"] * position["avg_cost"] + quantity * price
            ) / total_qty
        else:
            total_qty = quantity
            new_avg_cost = price
        upsert_position(conn, ticker, total_qty, new_avg_cost)
        new_cash = cash - cost
    elif side == "sell":
        held = position["quantity"] if position else 0.0
        if quantity > held + _CLOSE_EPSILON:
            raise TradeError(
                f"Insufficient shares: trying to sell {quantity} {ticker}, hold {held}"
            )
        remaining = held - quantity
        if remaining <= _CLOSE_EPSILON:
            delete_position(conn, ticker)
        else:
            upsert_position(conn, ticker, remaining, position["avg_cost"])
        new_cash = cash + quantity * price
    else:
        raise TradeError(f"Invalid side: {side!r}")

    update_cash_balance(conn, new_cash)
    add_trade(conn, ticker, side, quantity, price)

    total_value = await _total_value(conn, cache, new_cash)
    add_snapshot(conn, total_value)

    return {
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "cash_balance": new_cash,
        "total_value": total_value,
    }


async def _total_value(conn: sqlite3.Connection, cache: PriceCache, cash: float) -> float:
    total = cash
    for pos in list_positions(conn):
        state = await cache.get(pos["ticker"])
        if state is not None:
            total += pos["quantity"] * state.price
    return total


async def build_portfolio(conn: sqlite3.Connection, cache: PriceCache) -> PortfolioOut:
    """Assemble the portfolio view: positions priced from the cache, cash, and total value."""
    profile = get_profile(conn)
    cash = profile["cash_balance"]
    positions: list[PositionOut] = []
    total = cash
    total_unrealized = 0.0

    for pos in list_positions(conn):
        state = await cache.get(pos["ticker"])
        current_price = state.price if state else pos["avg_cost"]
        market_value = pos["quantity"] * current_price
        cost_basis = pos["quantity"] * pos["avg_cost"]
        unrealized = market_value - cost_basis
        pct = (unrealized / cost_basis * 100) if cost_basis else 0.0
        total += market_value
        total_unrealized += unrealized
        positions.append(
            PositionOut(
                ticker=pos["ticker"],
                quantity=pos["quantity"],
                avg_cost=round(pos["avg_cost"], 4),
                current_price=round(current_price, 4),
                unrealized_pnl=round(unrealized, 2),
                change_percent=round(pct, 2),
            )
        )

    return PortfolioOut(
        cash_balance=round(cash, 2),
        total_value=round(total, 2),
        unrealized_pnl=round(total_unrealized, 2),
        positions=positions,
    )
