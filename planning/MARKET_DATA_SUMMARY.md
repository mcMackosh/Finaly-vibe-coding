# Market Data — Summary

Status: complete. Implements the market data component from `PLAN.md` §6/§8, following the
detailed design in `MARKET_DATA_DESIGN.md`. Portfolio, watchlist persistence, and chat are not
part of this component and remain future work.

## What Was Built

`backend/` is a `uv`-managed FastAPI project (`uv.lock` committed):

- `app/market_data/models.py` — `PriceTick` (SSE wire format) and `PriceState` (cache snapshot)
- `app/market_data/tickers.py` — seed price/drift/volatility/sector table for the 10 default
  tickers (AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX)
- `app/market_data/base.py` — `MarketDataProvider` ABC (`start`/`stop`/`add_ticker`/`remove_ticker`)
- `app/market_data/cache.py` — `PriceCache`, an in-memory latest-state store with a pub/sub queue
  per subscriber, shared by every consumer (SSE endpoint, console demo)
- `app/market_data/simulator.py` — `SimulatedMarketDataProvider`: correlated geometric Brownian
  motion (one-factor-per-sector shock model) at a 500ms tick, plus occasional 2-5% "event" jumps
- `app/api/stream.py` — `GET /api/stream/prices`, an SSE endpoint streaming `PriceTick` JSON
  frames, with a 15s keep-alive comment for idle periods
- `app/api/health.py` — `GET /api/health`
- `app/main.py` — FastAPI app wiring the cache + simulator together via lifespan, starting the
  default 10-ticker watchlist on boot

The Massive (Polygon.io) REST client and the env-var-driven provider factory described in
`MARKET_DATA_DESIGN.md` §6/§7 were deliberately not built — there's no API key to build or test
against yet, and the simulator is the only provider in use. The `MarketDataProvider` ABC is in
place so swapping one in later doesn't touch anything downstream.

## Test Suite

`backend/tests/market_data/`, run with `uv run pytest` (13 tests, ~6s):

- **Simulator** — deterministic output under a seeded RNG, one tick per tracked ticker per step,
  no tick when nothing is tracked, prices stay positive across 10,000 steps, and tech-sector
  tickers show higher return correlation than tech-vs-finance (sanity check on the shock model)
- **Cache** — update/remove/get round-trip, a published tick reaches subscribed queues, an
  unsubscribed queue receives nothing further, multiple subscribers each get their own copy
- **Stream/lifecycle** — provider `start`/`add_ticker`/`remove_ticker`/`stop` lifecycle; an
  end-to-end test that boots the real FastAPI app on a real socket and asserts `/api/stream/prices`
  emits valid `PriceTick` JSON

Note: the SSE endpoint test runs against an actual `uvicorn` server rather than httpx's in-process
`ASGITransport` — the latter hangs on this streaming response (a testing-harness quirk, confirmed
by the fact the real server streams correctly under `curl`), so the test exercises the real
runtime path instead.

## Demo

Two ways to see it running:

```bash
cd backend
uv sync

# HTTP API + SSE stream — the data source a frontend chart would consume
uv run uvicorn app.main:app --reload
curl http://localhost:8000/api/health
curl -N http://localhost:8000/api/stream/prices

# terminal-only demo of the same price stream, consuming the cache's pub/sub queue
uv run python -m app.console
```

The console demo redraws a 10-ticker table once a second, colored green/red per tick direction —
a quick way to eyeball the simulator's correlated moves without a frontend.
