"""Shared in-memory price cache with pub/sub for streaming consumers."""

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
