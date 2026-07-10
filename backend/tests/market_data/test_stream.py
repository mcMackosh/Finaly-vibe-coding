import asyncio
import json
import socket

import httpx
import pytest
import uvicorn

from app.market_data.cache import PriceCache
from app.market_data.simulator import SimulatedMarketDataProvider


async def test_provider_start_stop_add_remove_lifecycle():
    cache = PriceCache()
    provider = SimulatedMarketDataProvider(cache)

    await provider.start(["AAPL"])
    await provider.add_ticker("MSFT")
    await provider.remove_ticker("AAPL")
    await provider.stop()

    assert await cache.get("AAPL") is None


@pytest.fixture
async def server_url():
    """Runs the real app on a real socket -- SSE streaming doesn't behave the same
    over httpx's in-process ASGI transport as it does over an actual connection."""
    from app.main import app

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except TimeoutError:
        task.cancel()


async def test_health_endpoint_returns_ok(server_url: str):
    async with httpx.AsyncClient(base_url=server_url) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_stream_endpoint_emits_valid_price_tick_json(server_url: str):
    async with httpx.AsyncClient(base_url=server_url, timeout=10.0) as client:
        async with client.stream("GET", "/api/stream/prices") as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line.removeprefix("data: "))
                assert payload["ticker"] in {
                    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
                    "NVDA", "META", "JPM", "V", "NFLX",
                }
                assert "price" in payload
                break
