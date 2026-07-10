import asyncio

import pytest

from app.market_data.cache import PriceCache
from app.market_data.models import PriceTick


def make_tick(ticker: str = "AAPL", price: float = 191.0, previous_price: float = 190.0) -> PriceTick:
    return PriceTick.build(ticker, price=price, previous_price=previous_price)


async def test_update_stores_latest_state():
    cache = PriceCache()
    await cache.update(make_tick())

    state = await cache.get("AAPL")

    assert state is not None
    assert state.price == 191.0
    assert state.previous_price == 190.0


async def test_remove_clears_state():
    cache = PriceCache()
    await cache.update(make_tick())
    await cache.remove("AAPL")

    assert await cache.get("AAPL") is None


async def test_subscriber_receives_published_tick():
    cache = PriceCache()
    queue = cache.subscribe()

    await cache.update(make_tick())

    tick = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert tick.ticker == "AAPL"


async def test_unsubscribed_queue_does_not_receive_further_ticks():
    cache = PriceCache()
    queue = cache.subscribe()
    cache.unsubscribe(queue)

    await cache.update(make_tick())

    assert queue.empty()


async def test_multiple_subscribers_each_get_the_tick():
    cache = PriceCache()
    queue_a = cache.subscribe()
    queue_b = cache.subscribe()

    await cache.update(make_tick())

    tick_a = await asyncio.wait_for(queue_a.get(), timeout=1.0)
    tick_b = await asyncio.wait_for(queue_b.get(), timeout=1.0)
    assert tick_a.ticker == tick_b.ticker == "AAPL"
