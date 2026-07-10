"""FastAPI app: wires the price cache + simulator and serves the SSE stream."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root so env vars are available in all contexts
# (local dev without Docker, Docker via --env-file, CI, etc.)
_dotenv = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_dotenv)
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.portfolio import router as portfolio_router
from app.api.stream import router as stream_router
from app.api.watchlist import router as watchlist_router
from app.database import db_conn, init_db, list_watchlist
from app.market_data.cache import PriceCache
from app.market_data.provider import create_provider
from app.market_data.tickers import DEFAULT_WATCHLIST


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    cache = PriceCache()
    provider = create_provider(cache)

    app.state.price_cache = cache
    app.state.market_data_provider = provider

    with db_conn() as conn:
        tickers = [row["ticker"] for row in list_watchlist(conn)] or DEFAULT_WATCHLIST
    await provider.start(tickers)

    yield

    await provider.stop()


app = FastAPI(title="FinAlly Backend", lifespan=lifespan)
app.include_router(health_router)
app.include_router(stream_router)
app.include_router(watchlist_router)
app.include_router(portfolio_router)
app.include_router(chat_router)

# Serve the static Next.js export (if built). Mounted last so API routes win.
# Defaults to <repo>/frontend/out; overridable via FRONTEND_DIR.
_frontend_dir = Path(
    os.environ.get("FRONTEND_DIR")
    or Path(__file__).resolve().parents[2] / "frontend" / "out"
)
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="static")
