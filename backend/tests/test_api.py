"""Tests for the REST API layer: trading core, portfolio, watchlist, and chat routes.

Trading logic is exercised directly (temp DB + seeded price cache) for deterministic
coverage of validation edges; the HTTP routes are driven in-process via httpx ASGI
transport with the market data provider stubbed and LLM_MOCK enabled.
"""

import httpx
import pytest

from app.market_data.cache import PriceCache
from app.market_data.models import PriceTick
from app.market_data.tickers import DEFAULT_WATCHLIST, profile_for

# Known prices so trade math is deterministic (not the moving simulator output).
SEED_PRICES = {t: profile_for(t).seed_price for t in DEFAULT_WATCHLIST}


async def _seed_cache() -> PriceCache:
    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        await cache.update(PriceTick.build(ticker, price=price, previous_price=price))
    return cache


@pytest.fixture
def db(tmp_path, monkeypatch):
    from app import database

    db_file = tmp_path / "test.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(db_file))
    monkeypatch.setenv("LLM_MOCK", "true")
    database.init_db(db_file)
    return db_file


@pytest.fixture
async def cache() -> PriceCache:
    return await _seed_cache()


@pytest.fixture
async def client(db, cache):
    """In-process client with app.state wired to the seeded cache and a stub provider."""
    from app.main import app
    from app.market_data.simulator import SimulatedMarketDataProvider

    app.state.price_cache = cache
    app.state.market_data_provider = SimulatedMarketDataProvider(cache)  # not started

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Trading core (direct) -------------------------------------------------

async def test_buy_updates_position_cash_and_snapshot(db, cache):
    from app.database import db_conn, get_position, get_profile, list_snapshots
    from app.trading import execute_trade

    with db_conn(db) as conn:
        result = await execute_trade(conn, cache, "AAPL", 10, "buy")

    assert result["price"] == SEED_PRICES["AAPL"]
    with db_conn(db) as conn:
        pos = get_position(conn, "AAPL")
        profile = get_profile(conn)
        snaps = list_snapshots(conn)
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == SEED_PRICES["AAPL"]
    assert profile["cash_balance"] == pytest.approx(10000 - 10 * SEED_PRICES["AAPL"])
    assert len(snaps) == 1


async def test_buy_recomputes_weighted_avg_cost(db, cache):
    from app.database import db_conn, get_position
    from app.trading import execute_trade

    with db_conn(db) as conn:
        await execute_trade(conn, cache, "TSLA", 2, "buy")  # @250
    # Move the price, buy more, expect weighted average.
    await cache.update(PriceTick.build("TSLA", price=350.0, previous_price=250.0))
    with db_conn(db) as conn:
        await execute_trade(conn, cache, "TSLA", 2, "buy")  # @350
        pos = get_position(conn, "TSLA")
    assert pos["quantity"] == 4
    assert pos["avg_cost"] == pytest.approx((2 * 250 + 2 * 350) / 4)


async def test_buy_insufficient_cash_raises(db, cache):
    from app.database import db_conn
    from app.trading import TradeError, execute_trade

    with pytest.raises(TradeError):
        with db_conn(db) as conn:
            await execute_trade(conn, cache, "NFLX", 1000, "buy")  # way over $10k


async def test_sell_more_than_held_raises(db, cache):
    from app.database import db_conn
    from app.trading import TradeError, execute_trade

    with db_conn(db) as conn:
        await execute_trade(conn, cache, "AAPL", 5, "buy")
    with pytest.raises(TradeError):
        with db_conn(db) as conn:
            await execute_trade(conn, cache, "AAPL", 6, "sell")


async def test_selling_entire_position_removes_row(db, cache):
    from app.database import db_conn, get_position
    from app.trading import execute_trade

    with db_conn(db) as conn:
        await execute_trade(conn, cache, "AAPL", 5, "buy")
        await execute_trade(conn, cache, "AAPL", 5, "sell")
        pos = get_position(conn, "AAPL")
    assert pos is None


# --- Portfolio routes ------------------------------------------------------

async def test_get_portfolio_initial_state(client):
    resp = await client.get("/api/portfolio")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cash_balance"] == 10000.0
    assert body["unrealized_pnl"] == 0.0
    assert body["positions"] == []


async def test_trade_route_buy_then_portfolio_reflects_position(client):
    resp = await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"}
    )
    assert resp.status_code == 200
    # The trade route returns the full updated portfolio.
    traded = resp.json()
    assert traded["cash_balance"] == pytest.approx(10000 - 10 * SEED_PRICES["AAPL"])

    portfolio = (await client.get("/api/portfolio")).json()
    assert portfolio["cash_balance"] == pytest.approx(10000 - 10 * SEED_PRICES["AAPL"])
    pos = next(p for p in portfolio["positions"] if p["ticker"] == "AAPL")
    assert pos["quantity"] == 10
    assert pos["current_price"] == SEED_PRICES["AAPL"]
    assert "change_percent" in pos


async def test_trade_route_insufficient_cash_returns_400(client):
    resp = await client.post(
        "/api/portfolio/trade", json={"ticker": "NFLX", "quantity": 1000, "side": "buy"}
    )
    assert resp.status_code == 400
    assert "cash" in resp.json()["detail"].lower()


async def test_history_route_grows_after_trades(client):
    await client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"}
    )
    history = (await client.get("/api/portfolio/history")).json()
    assert len(history) == 1
    assert "total_value" in history[0]


# --- Watchlist routes ------------------------------------------------------

async def test_get_watchlist_returns_seeded_tickers_with_prices(client):
    items = (await client.get("/api/watchlist")).json()
    tickers = {i["ticker"] for i in items}
    assert {"AAPL", "GOOGL", "MSFT"} <= tickers
    aapl = next(i for i in items if i["ticker"] == "AAPL")
    assert aapl["price"] == SEED_PRICES["AAPL"]
    assert "change_percent" in aapl


async def test_add_and_remove_watchlist_ticker(client):
    add = await client.post("/api/watchlist", json={"ticker": "pypl"})
    assert add.status_code == 200
    assert add.json()["ticker"] == "PYPL"

    tickers = {i["ticker"] for i in (await client.get("/api/watchlist")).json()}
    assert "PYPL" in tickers

    remove = await client.delete("/api/watchlist/PYPL")
    assert remove.status_code == 200
    tickers = {i["ticker"] for i in (await client.get("/api/watchlist")).json()}
    assert "PYPL" not in tickers


async def test_remove_unknown_watchlist_ticker_returns_404(client):
    resp = await client.delete("/api/watchlist/ZZZZ")
    assert resp.status_code == 404


# --- Chat routes (mock LLM) ------------------------------------------------

async def test_chat_plain_message_returns_response(client):
    resp = await client.post("/api/chat", json={"message": "hello there"})
    assert resp.status_code == 200
    body = resp.json()
    assert "hello there" in body["message"]
    assert body["actions"]["trades"] == []
    assert body["actions"]["error"] is None


async def test_chat_buy_phrase_auto_executes_trade(client):
    resp = await client.post("/api/chat", json={"message": "please buy 3 AAPL now"})
    assert resp.status_code == 200
    trades = resp.json()["actions"]["trades"]
    assert len(trades) == 1
    assert trades[0]["ticker"] == "AAPL"

    portfolio = (await client.get("/api/portfolio")).json()
    pos = next(p for p in portfolio["positions"] if p["ticker"] == "AAPL")
    assert pos["quantity"] == 3


async def test_chat_history_records_user_and_assistant(client):
    await client.post("/api/chat", json={"message": "hi"})
    history = (await client.get("/api/chat/history")).json()
    roles = [m["role"] for m in history]
    assert roles == ["user", "assistant"]
    assert all("id" in m for m in history)
    assistant = history[1]
    assert assistant["actions"]["trades"] == []
