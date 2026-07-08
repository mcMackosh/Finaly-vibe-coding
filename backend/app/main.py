"""FastAPI app: wires the price cache + simulator and serves the SSE stream."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.stream import router as stream_router
from app.market_data.cache import PriceCache
from app.market_data.simulator import SimulatedMarketDataProvider
from app.market_data.tickers import DEFAULT_WATCHLIST


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    provider = SimulatedMarketDataProvider(cache)

    app.state.price_cache = cache
    app.state.market_data_provider = provider

    await provider.start(DEFAULT_WATCHLIST)

    yield

    await provider.stop()


app = FastAPI(title="FinAlly Backend", lifespan=lifespan)
app.include_router(health_router)
app.include_router(stream_router)
