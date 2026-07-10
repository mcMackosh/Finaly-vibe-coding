"""Massive (Polygon.io) REST polling provider.

Polls the snapshot endpoint for the union of watched tickers on a fixed interval and
pushes the results into the shared PriceCache as PriceTicks — the same output shape the
simulator produces, so nothing downstream needs to know which provider is running.
"""

import asyncio
import os
from collections.abc import Iterable

import httpx

from app.market_data.base import MarketDataProvider
from app.market_data.cache import PriceCache
from app.market_data.models import PriceTick

DEFAULT_BASE_URL = "https://api.polygon.io"
FREE_TIER_POLL_SECONDS = 15.0


class MassiveMarketDataProvider(MarketDataProvider):
    """REST polling client for Massive/Polygon.io.

    Auth and endpoints follow Polygon's v2 snapshot API. Base URL and poll interval are
    configurable via env vars so paid tiers can poll faster.
    """

    def __init__(
        self,
        cache: PriceCache,
        api_key: str,
        base_url: str | None = None,
        poll_interval: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(cache)
        self._api_key = api_key
        self._base_url = (base_url or os.getenv("MASSIVE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._poll_interval = poll_interval or float(
            os.getenv("MASSIVE_POLL_INTERVAL", FREE_TIER_POLL_SECONDS)
        )
        self._client = client
        self._owns_client = client is None
        self._tickers: set[str] = set()
        self._last_prices: dict[str, float] = {}
        self._task: asyncio.Task | None = None

    async def start(self, tickers: Iterable[str]) -> None:
        self._tickers = {t.upper() for t in tickers}
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker.upper())

    async def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker.upper())
        self._last_prices.pop(ticker.upper(), None)
        await self._cache.remove(ticker.upper())

    async def _run_loop(self) -> None:
        try:
            while True:
                for tick in await self._poll_once():
                    await self._cache.update(tick)
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            raise

    async def _poll_once(self) -> list[PriceTick]:
        if not self._tickers:
            return []
        url = f"{self._base_url}/v2/snapshot/locale/us/markets/stocks/tickers"
        params = {"tickers": ",".join(sorted(self._tickers)), "apiKey": self._api_key}
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return self._parse(response.json())

    def _parse(self, payload: dict) -> list[PriceTick]:
        """Turn a Polygon snapshot payload into PriceTicks.

        previous_price is the price from our last poll (so `change` reflects movement since
        the last tick we emitted), falling back to the snapshot's prevDay close on first sight.
        """
        ticks: list[PriceTick] = []
        for entry in payload.get("tickers", []):
            ticker = entry.get("ticker")
            price = _extract_price(entry)
            if ticker is None or price is None:
                continue
            previous = self._last_prices.get(ticker, _prev_day_close(entry) or price)
            self._last_prices[ticker] = price
            ticks.append(PriceTick.build(ticker, price=price, previous_price=previous))
        return ticks


def _extract_price(entry: dict) -> float | None:
    last_trade = entry.get("lastTrade") or {}
    if last_trade.get("p") is not None:
        return float(last_trade["p"])
    day = entry.get("day") or {}
    if day.get("c"):
        return float(day["c"])
    return None


def _prev_day_close(entry: dict) -> float | None:
    prev_day = entry.get("prevDay") or {}
    close = prev_day.get("c")
    return float(close) if close else None
