"""Simulated market data provider: correlated geometric Brownian motion."""

import asyncio
import math
import random
from collections.abc import Iterable

from app.market_data.cache import PriceCache
from app.market_data.models import PriceTick
from app.market_data.tickers import profile_for

UPDATE_INTERVAL_SECONDS = 0.5
SECONDS_PER_TRADING_YEAR = 252 * 6.5 * 3600  # 252 sessions, 6.5h each

BETA_MARKET = 0.5
BETA_SECTOR = 0.3
BETA_IDIO = math.sqrt(max(0.0, 1 - BETA_MARKET**2 - BETA_SECTOR**2))

EVENT_PROBABILITY_PER_TICK = 0.0006   # ~a couple of "surprise" moves per ticker per hour
EVENT_MAGNITUDE_RANGE = (0.02, 0.05)  # 2-5% jump


class SimulatedMarketDataProvider:
    def __init__(self, cache: PriceCache, rng: random.Random | None = None) -> None:
        self._cache = cache
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

    def _seed(self, ticker: str) -> None:
        if ticker not in self._prices:
            self._prices[ticker] = profile_for(ticker).seed_price

    async def _run_loop(self) -> None:
        dt = UPDATE_INTERVAL_SECONDS / SECONDS_PER_TRADING_YEAR
        try:
            while True:
                await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
                await self._step(dt)
        except asyncio.CancelledError:
            raise

    async def _step(self, dt: float) -> None:
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
            await self._cache.update(tick)
