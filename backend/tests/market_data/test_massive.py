"""Tests for the Massive (Polygon.io) provider and the env-var provider factory."""

import httpx
import pytest

from app.market_data.cache import PriceCache
from app.market_data.massive_client import MassiveMarketDataProvider
from app.market_data.provider import create_provider
from app.market_data.simulator import SimulatedMarketDataProvider

_SNAPSHOT = {
    "tickers": [
        {"ticker": "AAPL", "lastTrade": {"p": 191.5}, "prevDay": {"c": 189.0}},
        {"ticker": "MSFT", "lastTrade": {"p": 421.0}, "prevDay": {"c": 420.0}},
    ]
}


def test_factory_uses_simulator_without_key(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    provider = create_provider(PriceCache())
    assert isinstance(provider, SimulatedMarketDataProvider)


def test_factory_uses_massive_with_key(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key")
    provider = create_provider(PriceCache())
    assert isinstance(provider, MassiveMarketDataProvider)


def test_factory_treats_blank_key_as_absent(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "   ")
    provider = create_provider(PriceCache())
    assert isinstance(provider, SimulatedMarketDataProvider)


def test_parse_uses_prev_day_close_on_first_sight():
    provider = MassiveMarketDataProvider(PriceCache(), api_key="k")
    ticks = provider._parse(_SNAPSHOT)
    by_ticker = {t.ticker: t for t in ticks}
    assert by_ticker["AAPL"].price == 191.5
    assert by_ticker["AAPL"].previous_price == 189.0  # prevDay close on first poll
    assert by_ticker["MSFT"].price == 421.0


def test_parse_uses_last_price_as_previous_on_second_poll():
    provider = MassiveMarketDataProvider(PriceCache(), api_key="k")
    provider._parse(_SNAPSHOT)
    second = {"tickers": [{"ticker": "AAPL", "lastTrade": {"p": 200.0}, "prevDay": {"c": 189.0}}]}
    tick = provider._parse(second)[0]
    assert tick.price == 200.0
    assert tick.previous_price == 191.5  # last polled price, not prevDay


def test_parse_skips_entries_without_price():
    provider = MassiveMarketDataProvider(PriceCache(), api_key="k")
    ticks = provider._parse({"tickers": [{"ticker": "AAPL"}, {"lastTrade": {"p": 1.0}}]})
    assert ticks == []


async def test_poll_once_reads_snapshot_via_mocked_client():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "AAPL" in request.url.params["tickers"]
        assert request.url.params["apiKey"] == "test-key"
        return httpx.Response(200, json=_SNAPSHOT)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = MassiveMarketDataProvider(
        PriceCache(), api_key="test-key", client=client
    )
    provider._tickers = {"AAPL", "MSFT"}
    ticks = await provider._poll_once()
    await client.aclose()
    assert {t.ticker for t in ticks} == {"AAPL", "MSFT"}
