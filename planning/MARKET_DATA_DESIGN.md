# Market Data Backend — Detailed Design

This document expands §6 (Market Data) of `PLAN.md` into an implementable design: a unified
provider interface, a simulator built on correlated geometric Brownian motion, a Massive
(Polygon.io) REST polling client, the shared in-memory price cache, and the SSE streaming
endpoint that ties them together. Code samples are illustrative Python/FastAPI — adjust names
to match whatever internal module layout the Backend Engineer settles on, but keep the
interface boundary described here so the simulator and Massive client stay interchangeable.

## 1. Module Layout

```
backend/
├── app/
│   ├── market_data/
│   │   ├── __init__.py
│   │   ├── models.py          # PriceTick, PriceState
│   │   ├── base.py            # MarketDataProvider ABC
│   │   ├── cache.py           # PriceCache + Broadcaster (pub/sub for SSE)
│   │   ├── tickers.py         # seed price / drift / vol / sector table
│   │   ├── simulator.py       # SimulatedMarketDataProvider (GBM)
│   │   ├── massive_client.py  # MassiveMarketDataProvider (REST polling)
│   │   └── factory.py         # env-var based provider selection
│   ├── api/
│   │   └── stream.py          # GET /api/stream/prices
│   ├── config.py
│   └── main.py                # FastAPI app + lifespan wiring
└── tests/
    └── market_data/
        ├── test_simulator.py
        ├── test_massive_client.py
        ├── test_cache.py
        └── test_stream.py
```

Everything outside `market_data/` (portfolio valuation, watchlist CRUD, the SSE route) talks
only to `PriceCache` and the `MarketDataProvider` interface — never to `SimulatedMarketDataProvider`
or `MassiveMarketDataProvider` directly. That's what makes the source swappable via one env var.

---

## 2. Data Models

```python
# app/market_data/models.py
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class PriceTick(BaseModel):
    """One price update for one ticker — the unit both providers emit and the SSE wire format."""

    ticker: str
    price: float
    previous_price: float
    change: float
    change_percent: float
    direction: Direction
    timestamp: datetime

    @classmethod
    def build(cls, ticker: str, price: float, previous_price: float) -> "PriceTick":
        change = price - previous_price
        return cls(
            ticker=ticker,
            price=round(price, 4),
            previous_price=round(previous_price, 4),
            change=round(change, 4),
            change_percent=round((change / previous_price) * 100, 4) if previous_price else 0.0,
            direction=Direction.UP if change > 0 else Direction.DOWN if change < 0 else Direction.FLAT,
            timestamp=datetime.now(timezone.utc),
        )


class PriceState(BaseModel):
    """Latest known state for a ticker, as held in the cache and returned by REST endpoints."""

    ticker: str
    price: float
    previous_price: float
    updated_at: datetime
```

`PriceTick` is what gets pushed over SSE (matches PLAN.md §6: "ticker, price, previous price,
timestamp, and change direction"). `PriceState` is what REST endpoints like `/api/watchlist` and
`/api/portfolio` read out of the cache to compute current values — they don't need `change_percent`
recomputed on every read since the frontend derives its own deltas from the stream.

---

## 3. The Unified Provider Interface

```python
# app/market_data/base.py
from abc import ABC, abstractmethod
from collections.abc import Iterable

from app.market_data.cache import PriceCache


class MarketDataProvider(ABC):
    """Either a simulator or a real data client. Both push ticks into the same PriceCache;
    nothing downstream needs to know which implementation is running."""

    def __init__(self, cache: PriceCache) -> None:
        self._cache = cache

    @abstractmethod
    async def start(self, tickers: Iterable[str]) -> None:
        """Begin producing price updates for the given initial ticker set."""

    @abstractmethod
    async def stop(self) -> None:
        """Cancel background work and release resources (used on app shutdown)."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Start tracking a ticker that was just added to the watchlist."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Stop tracking a ticker that was just removed from the watchlist."""
```

Both concrete providers own exactly one `asyncio.Task` background loop, started in `start()` and
cancelled in `stop()`. `add_ticker`/`remove_ticker` mutate the loop's working set without
restarting it — the watchlist API route calls these directly after writing to SQLite (see §7).

---

## 4. Shared Price Cache + Broadcaster

The cache is the single source of truth both REST endpoints and the SSE stream read from. The
broadcaster is a lightweight pub/sub layer so multiple SSE connections (today: the one browser
tab; tomorrow: multi-user) each get their own queue of ticks without the provider needing to know
how many listeners exist.

```python
# app/market_data/cache.py
import asyncio
from app.market_data.models import PriceState, PriceTick


class PriceCache:
    def __init__(self) -> None:
        self._state: dict[str, PriceState] = {}
        self._lock = asyncio.Lock()
        self._subscribers: set[asyncio.Queue[PriceTick]] = set()

    async def update(self, tick: PriceTick) -> None:
        async with self._lock:
            self._state[tick.ticker] = PriceState(
                ticker=tick.ticker,
                price=tick.price,
                previous_price=tick.previous_price,
                updated_at=tick.timestamp,
            )
        self._publish(tick)

    async def remove(self, ticker: str) -> None:
        async with self._lock:
            self._state.pop(ticker, None)

    async def get(self, ticker: str) -> PriceState | None:
        async with self._lock:
            return self._state.get(ticker)

    async def get_all(self) -> dict[str, PriceState]:
        async with self._lock:
            return dict(self._state)

    def subscribe(self) -> "asyncio.Queue[PriceTick]":
        queue: asyncio.Queue[PriceTick] = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: "asyncio.Queue[PriceTick]") -> None:
        self._subscribers.discard(queue)

    def _publish(self, tick: PriceTick) -> None:
        for queue in self._subscribers:
            try:
                queue.put_nowait(tick)
            except asyncio.QueueFull:
                # A stalled client shouldn't block ticks for everyone else; drop for that one.
                pass
```

`PriceCache` is instantiated once in `main.py`'s lifespan and stashed on `app.state`, so both the
provider and every route handler share the same instance.

---

## 5. Simulator — Correlated GBM

### 5.1 Ticker profile table

Every ticker needs a seed price, an annual drift (`mu`), an annual volatility (`sigma`), and a
sector tag used for correlated moves. The ten defaults from PLAN.md §7 are seeded explicitly;
anything a user adds later (via watchlist UI or chat) falls back to a generic profile.

```python
# app/market_data/tickers.py
from dataclasses import dataclass


@dataclass(frozen=True)
class TickerProfile:
    seed_price: float
    mu: float       # annual drift
    sigma: float    # annual volatility
    sector: str


TICKER_PROFILES: dict[str, TickerProfile] = {
    "AAPL":  TickerProfile(190.0, mu=0.08, sigma=0.28, sector="tech"),
    "GOOGL": TickerProfile(175.0, mu=0.07, sigma=0.30, sector="tech"),
    "MSFT":  TickerProfile(420.0, mu=0.09, sigma=0.25, sector="tech"),
    "AMZN":  TickerProfile(185.0, mu=0.10, sigma=0.32, sector="tech"),
    "TSLA":  TickerProfile(250.0, mu=0.05, sigma=0.55, sector="auto"),
    "NVDA":  TickerProfile(120.0, mu=0.15, sigma=0.50, sector="tech"),
    "META":  TickerProfile(500.0, mu=0.09, sigma=0.35, sector="tech"),
    "JPM":   TickerProfile(200.0, mu=0.06, sigma=0.20, sector="finance"),
    "V":     TickerProfile(275.0, mu=0.07, sigma=0.18, sector="finance"),
    "NFLX":  TickerProfile(650.0, mu=0.08, sigma=0.33, sector="media"),
}

DEFAULT_PROFILE = TickerProfile(seed_price=100.0, mu=0.06, sigma=0.30, sector="other")


def profile_for(ticker: str) -> TickerProfile:
    return TICKER_PROFILES.get(ticker.upper(), DEFAULT_PROFILE)
```

### 5.2 Correlated step generation

Rather than maintaining a full covariance matrix, use a one-factor-per-sector model: draw one
market-wide shock and one shock per active sector each tick, then blend them with each ticker's
own idiosyncratic noise. This is what produces "tech stocks move together" cheaply.

```python
# app/market_data/simulator.py
import asyncio
import math
import random
from collections.abc import Iterable

from app.market_data.base import MarketDataProvider
from app.market_data.cache import PriceCache
from app.market_data.models import PriceTick
from app.market_data.tickers import profile_for

UPDATE_INTERVAL_SECONDS = 0.5
SECONDS_PER_TRADING_YEAR = 252 * 6.5 * 3600  # 252 sessions, 6.5h each

BETA_MARKET = 0.5
BETA_SECTOR = 0.3
BETA_IDIO = math.sqrt(max(0.0, 1 - BETA_MARKET**2 - BETA_SECTOR**2))  # keeps shock variance ~1

EVENT_PROBABILITY_PER_TICK = 0.0006   # ~a couple of "surprise" moves per ticker per hour
EVENT_MAGNITUDE_RANGE = (0.02, 0.05)  # 2-5% jump, per PLAN.md


class SimulatedMarketDataProvider(MarketDataProvider):
    def __init__(self, cache: PriceCache, rng: random.Random | None = None) -> None:
        super().__init__(cache)
        self._rng = rng or random.Random()
        self._prices: dict[str, float] = {}
        self._task: asyncio.Task | None = None

    async def start(self, tickers: Iterable[str]) -> None:
        for ticker in tickers:
            self._seed(ticker)
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def add_ticker(self, ticker: str) -> None:
        self._seed(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self._prices.pop(ticker, None)
        await self._cache.remove(ticker)

    def _seed(self, ticker: str) -> None:
        if ticker not in self._prices:
            self._prices[ticker] = profile_for(ticker).seed_price

    async def _run_loop(self) -> None:
        dt = UPDATE_INTERVAL_SECONDS / SECONDS_PER_TRADING_YEAR
        try:
            while True:
                await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
                self._step(dt)
        except asyncio.CancelledError:
            raise

    def _step(self, dt: float) -> None:
        tickers = list(self._prices.keys())
        if not tickers:
            return

        market_shock = self._rng.gauss(0, 1)
        sector_shocks: dict[str, float] = {}

        for ticker in tickers:
            profile = profile_for(ticker)
            sector_shock = sector_shocks.setdefault(profile.sector, self._rng.gauss(0, 1))
            idio_shock = self._rng.gauss(0, 1)
            shock = BETA_MARKET * market_shock + BETA_SECTOR * sector_shock + BETA_IDIO * idio_shock

            previous_price = self._prices[ticker]
            drift = (profile.mu - 0.5 * profile.sigma**2) * dt
            diffusion = profile.sigma * math.sqrt(dt) * shock
            new_price = previous_price * math.exp(drift + diffusion)

            if self._rng.random() < EVENT_PROBABILITY_PER_TICK:
                magnitude = self._rng.uniform(*EVENT_MAGNITUDE_RANGE)
                sign = self._rng.choice((-1, 1))
                new_price *= 1 + sign * magnitude

            new_price = max(new_price, 0.01)
            self._prices[ticker] = new_price

            tick = PriceTick.build(ticker, price=new_price, previous_price=previous_price)
            asyncio.create_task(self._cache.update(tick))
```

Notes:
- All tracked tickers are advanced in the same `_step()` call using the same `market_shock`, which
  is what makes moves correlated instead of independent per-ticker random walks.
- `BETA_IDIO` is derived so the combined shock keeps unit variance regardless of the two chosen
  betas — tune `BETA_MARKET`/`BETA_SECTOR` to make correlation looser or tighter.
- The random "event" is a bonus multiplicative jump layered on top of the regular GBM step, not a
  replacement for it — kept small-probability so it reads as occasional drama, not chaos.
- Passing an explicit `rng` (seeded `random.Random`) is what makes the unit tests deterministic
  (see §8).

---

## 6. Massive (Polygon.io) Client — REST Polling

This implements the same interface via polling rather than a background math loop. The exact
endpoint/response shape below should be verified against Massive's actual docs when a real API key
is available — the parsing logic is isolated in one method (`_parse_snapshot`) specifically so
that adjustment is a one-function change.

```python
# app/market_data/massive_client.py
import asyncio
import logging
from collections.abc import Iterable

import httpx

from app.market_data.base import MarketDataProvider
from app.market_data.cache import PriceCache
from app.market_data.models import PriceTick

logger = logging.getLogger(__name__)

MASSIVE_BASE_URL = "https://api.massive.io"  # placeholder — confirm against Massive docs
# Free tier: 5 calls/min -> poll every 15s. Paid tiers can poll every 2-15s (PLAN.md §6).
DEFAULT_POLL_INTERVAL_SECONDS = 15.0


class MassiveMarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        cache: PriceCache,
        api_key: str,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(cache)
        self._api_key = api_key
        self._poll_interval = poll_interval_seconds
        self._client = client or httpx.AsyncClient(base_url=MASSIVE_BASE_URL, timeout=10.0)
        self._tickers: set[str] = set()
        self._last_prices: dict[str, float] = {}
        self._task: asyncio.Task | None = None

    async def start(self, tickers: Iterable[str]) -> None:
        self._tickers = set(tickers)
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()

    async def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker)
        self._last_prices.pop(ticker, None)
        await self._cache.remove(ticker)

    async def _run_loop(self) -> None:
        backoff = self._poll_interval
        try:
            while True:
                if self._tickers:
                    try:
                        await self._poll_once()
                        backoff = self._poll_interval
                    except httpx.HTTPError as exc:
                        logger.warning("Massive API poll failed: %s", exc)
                        backoff = min(backoff * 2, self._poll_interval * 8)
                await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            raise

    async def _poll_once(self) -> None:
        tickers = list(self._tickers)
        response = await self._client.get(
            "/v2/snapshot/locale/us/markets/stocks/tickers",
            params={"tickers": ",".join(tickers), "apiKey": self._api_key},
        )
        response.raise_for_status()
        for ticker, price in self._parse_snapshot(response.json()).items():
            previous_price = self._last_prices.get(ticker, price)
            self._last_prices[ticker] = price
            tick = PriceTick.build(ticker, price=price, previous_price=previous_price)
            await self._cache.update(tick)

    @staticmethod
    def _parse_snapshot(payload: dict) -> dict[str, float]:
        """Isolated so response-shape changes only touch this method."""
        prices: dict[str, float] = {}
        for entry in payload.get("tickers", []):
            ticker = entry.get("ticker")
            last_trade = entry.get("lastTrade", {})
            price = last_trade.get("p")
            if ticker and price is not None:
                prices[ticker] = float(price)
        return prices
```

Design points:
- One poll fetches the union of all tracked tickers in a single request (PLAN.md §6: "Polls for
  the union of all watched tickers on a configurable interval") — never one request per ticker.
- Exponential backoff on failure, capped at 8x the base interval, so a transient outage doesn't
  spam a rate-limited free-tier key; it recovers to the normal interval as soon as a poll succeeds.
- `previous_price` defaults to the same price on the very first observation of a ticker (no
  synthetic prior tick), so the first `PriceTick` reports a flat/zero change instead of a bogus
  delta from 0.
- `poll_interval_seconds` is a constructor param, not hardcoded, so it can be driven by a
  `MASSIVE_POLL_INTERVAL_SECONDS` env var for accounts on a paid tier without touching code.

---

## 7. Provider Selection + FastAPI Wiring

```python
# app/market_data/factory.py
import os

from app.market_data.base import MarketDataProvider
from app.market_data.cache import PriceCache
from app.market_data.massive_client import MassiveMarketDataProvider
from app.market_data.simulator import SimulatedMarketDataProvider


def create_market_data_provider(cache: PriceCache) -> MarketDataProvider:
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()
    if api_key:
        poll_interval = float(os.getenv("MASSIVE_POLL_INTERVAL_SECONDS", "15"))
        return MassiveMarketDataProvider(cache, api_key=api_key, poll_interval_seconds=poll_interval)
    return SimulatedMarketDataProvider(cache)
```

```python
# app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.watchlist import get_watchlist_tickers  # returns list[str] from SQLite
from app.market_data.cache import PriceCache
from app.market_data.factory import create_market_data_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    provider = create_market_data_provider(cache)

    app.state.price_cache = cache
    app.state.market_data_provider = provider

    initial_tickers = await get_watchlist_tickers()
    await provider.start(initial_tickers)

    yield

    await provider.stop()


app = FastAPI(lifespan=lifespan)
```

The watchlist route calls the provider directly after writing to SQLite, so the two stay in sync:

```python
# app/api/watchlist.py (excerpt)
@router.post("/api/watchlist")
async def add_to_watchlist(body: AddTickerRequest, request: Request):
    await db_add_watchlist_ticker(body.ticker)
    await request.app.state.market_data_provider.add_ticker(body.ticker)
    return {"ticker": body.ticker}


@router.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str, request: Request):
    await db_remove_watchlist_ticker(ticker)
    await request.app.state.market_data_provider.remove_ticker(ticker)
    return {"ticker": ticker}
```

---

## 8. SSE Streaming Endpoint

```python
# app/api/stream.py
import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

KEEPALIVE_SECONDS = 15.0


@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    cache = request.app.state.price_cache
    queue = cache.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    tick = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                    yield f"data: {tick.model_dump_json()}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            cache.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

- One `PriceTick` becomes one SSE `data:` frame — the frontend's `EventSource.onmessage` parses
  `event.data` as JSON directly into `{ticker, price, previous_price, change, change_percent,
  direction, timestamp}` (matches the fields required by PLAN.md §6 and the flash/sparkline logic
  in §10).
- The keep-alive comment line (`:` prefix, ignored by `EventSource`) prevents idle-timeout
  disconnects through proxies during quiet periods — irrelevant for the simulator (always ticking)
  but matters once Massive's 15s poll interval is in play.
- `request.is_disconnected()` plus `finally: cache.unsubscribe(queue)` keeps the subscriber set
  from leaking when a browser tab closes.
- No client-side retry logic is needed — `EventSource` reconnects automatically per PLAN.md §10;
  the frontend only needs `onopen`/`onerror` to drive the connection-status dot.

---

## 9. Testing Strategy

```python
# tests/market_data/test_simulator.py
import random
import pytest

from app.market_data.cache import PriceCache
from app.market_data.simulator import SimulatedMarketDataProvider


@pytest.mark.asyncio
async def test_step_is_deterministic_with_seeded_rng():
    cache = PriceCache()
    sim_a = SimulatedMarketDataProvider(cache, rng=random.Random(42))
    sim_b = SimulatedMarketDataProvider(cache, rng=random.Random(42))
    sim_a._seed("AAPL")
    sim_b._seed("AAPL")

    dt = 0.5 / (252 * 6.5 * 3600)
    sim_a._step(dt)
    sim_b._step(dt)

    assert sim_a._prices["AAPL"] == sim_b._prices["AAPL"]


@pytest.mark.asyncio
async def test_prices_never_go_negative_across_many_steps():
    cache = PriceCache()
    sim = SimulatedMarketDataProvider(cache, rng=random.Random(1))
    sim._seed("TSLA")  # highest sigma in the table — most likely to stress the floor
    dt = 0.5 / (252 * 6.5 * 3600)
    for _ in range(10_000):
        sim._step(dt)
    assert sim._prices["TSLA"] > 0
```

```python
# tests/market_data/test_massive_client.py
import httpx
import pytest
import respx

from app.market_data.cache import PriceCache
from app.market_data.massive_client import MassiveMarketDataProvider

SNAPSHOT_FIXTURE = {
    "tickers": [
        {"ticker": "AAPL", "lastTrade": {"p": 191.23}},
        {"ticker": "GOOGL", "lastTrade": {"p": 176.10}},
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_poll_once_updates_cache():
    respx.get(url__regex=r".*/v2/snapshot/.*").mock(
        return_value=httpx.Response(200, json=SNAPSHOT_FIXTURE)
    )
    cache = PriceCache()
    provider = MassiveMarketDataProvider(cache, api_key="test-key")
    provider._tickers = {"AAPL", "GOOGL"}

    await provider._poll_once()

    state = await cache.get("AAPL")
    assert state is not None
    assert state.price == 191.23
```

```python
# tests/market_data/test_stream.py
# Conformance test run against BOTH providers to guarantee interface parity.
import pytest

from app.market_data.cache import PriceCache
from app.market_data.simulator import SimulatedMarketDataProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_factory", [
    lambda cache: SimulatedMarketDataProvider(cache),
    # MassiveMarketDataProvider included here too, constructed with a respx-mocked client
])
async def test_provider_start_stop_add_remove_lifecycle(provider_factory):
    cache = PriceCache()
    provider = provider_factory(cache)
    await provider.start(["AAPL"])
    await provider.add_ticker("MSFT")
    await provider.remove_ticker("AAPL")
    await provider.stop()
```

Key things unit tests must cover (per PLAN.md §12):
- GBM math produces valid, bounded prices and is reproducible under a seeded RNG.
- Correlated moves: a statistical test asserting tech-sector tickers have higher return
  correlation than tech-vs-finance over many simulated steps (sanity check on the factor model,
  not an exact-value assertion).
- Massive response parsing against fixture JSON, including a malformed/partial payload (missing
  `lastTrade`) to confirm it's skipped rather than raising.
- Both providers conform to `MarketDataProvider` (same lifecycle test parametrized over both).
- Cache/broadcaster: a published tick reaches all current subscribers and not ones that already
  unsubscribed.
- SSE endpoint integration test: connect with an `httpx.AsyncClient` against the streaming route,
  assert the first line(s) parse as valid `PriceTick` JSON.

---

## 10. Config Recap

| Env var | Effect |
|---|---|
| `MASSIVE_API_KEY` | If set & non-empty → `MassiveMarketDataProvider`; otherwise → `SimulatedMarketDataProvider` |
| `MASSIVE_POLL_INTERVAL_SECONDS` | Overrides the default 15s poll interval (lower for paid tiers) |

No simulator-specific env vars are needed — its tuning constants (`UPDATE_INTERVAL_SECONDS`,
`BETA_MARKET`, `EVENT_PROBABILITY_PER_TICK`, the ticker profile table) are code constants, since
they're demo-quality tuning knobs rather than deployment configuration.

## 11. Multi-User Extensibility

Nothing here assumes a single user except the fact that today only one watchlist exists in
SQLite (`user_id="default"`, per PLAN.md §7). `PriceCache` already supports arbitrary numbers of
SSE subscribers, and both providers track tickers as a global set rather than per-connection —
adding multi-user support later means broadcasting per-user watchlists filtered from the same
shared cache, not rearchitecting the market data layer itself.
