"""Provider interface every market data source implements."""

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
