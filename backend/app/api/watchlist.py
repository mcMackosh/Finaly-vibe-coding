"""Watchlist REST endpoints (PLAN.md §8).

Adding/removing a ticker also tells the market data provider to start/stop tracking it,
so a freshly added ticker begins streaming without a restart.
"""

from fastapi import APIRouter, HTTPException, Request

from app.database import add_to_watchlist, db_conn, list_watchlist, remove_from_watchlist
from app.models import WatchlistAddRequest, WatchlistItemOut

router = APIRouter(prefix="/api/watchlist")


def _item(ticker: str, state) -> WatchlistItemOut:
    if state is None:
        return WatchlistItemOut(ticker=ticker)
    change_percent = (
        round((state.price - state.previous_price) / state.previous_price * 100, 4)
        if state.previous_price
        else 0.0
    )
    return WatchlistItemOut(
        ticker=ticker,
        price=state.price,
        previous_price=state.previous_price,
        change_percent=change_percent,
    )


@router.get("")
async def get_watchlist(request: Request) -> list[WatchlistItemOut]:
    cache = request.app.state.price_cache
    with db_conn() as conn:
        rows = list_watchlist(conn)
    return [_item(row["ticker"], await cache.get(row["ticker"])) for row in rows]


@router.post("")
async def post_watchlist(request: Request, body: WatchlistAddRequest) -> WatchlistItemOut:
    ticker = body.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")

    with db_conn() as conn:
        add_to_watchlist(conn, ticker)

    await request.app.state.market_data_provider.add_ticker(ticker)
    state = await request.app.state.price_cache.get(ticker)
    return _item(ticker, state)


@router.delete("/{ticker}")
async def delete_watchlist(request: Request, ticker: str) -> dict:
    ticker = ticker.strip().upper()
    with db_conn() as conn:
        removed = remove_from_watchlist(conn, ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist")

    await request.app.state.market_data_provider.remove_ticker(ticker)
    return {"removed": ticker}
