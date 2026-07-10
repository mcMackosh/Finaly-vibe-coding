"""Env-var-driven factory selecting the market data provider.

If MASSIVE_API_KEY is set and non-empty, use the Massive (Polygon.io) REST client;
otherwise fall back to the built-in simulator.
"""

import os

from app.market_data.base import MarketDataProvider
from app.market_data.cache import PriceCache
from app.market_data.massive_client import MassiveMarketDataProvider
from app.market_data.simulator import SimulatedMarketDataProvider


def create_provider(cache: PriceCache) -> MarketDataProvider:
    api_key = os.getenv("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveMarketDataProvider(cache, api_key=api_key)
    return SimulatedMarketDataProvider(cache)
