"""Portfolio REST endpoints (PLAN.md §8): current holdings, trade execution, value history."""

from fastapi import APIRouter, HTTPException, Request

from app.database import db_conn, list_snapshots
from app.models import PortfolioOut, SnapshotOut, TradeRequest
from app.trading import TradeError, build_portfolio, execute_trade

router = APIRouter(prefix="/api/portfolio")


@router.get("")
async def get_portfolio(request: Request) -> PortfolioOut:
    with db_conn() as conn:
        return await build_portfolio(conn, request.app.state.price_cache)


@router.post("/trade")
async def post_trade(request: Request, body: TradeRequest) -> PortfolioOut:
    cache = request.app.state.price_cache
    try:
        with db_conn() as conn:
            await execute_trade(conn, cache, body.ticker, body.quantity, body.side)
            return await build_portfolio(conn, cache)
    except TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/history")
async def get_history(request: Request) -> list[SnapshotOut]:
    with db_conn() as conn:
        snapshots = list_snapshots(conn)
    return [
        SnapshotOut(total_value=s["total_value"], recorded_at=s["recorded_at"])
        for s in snapshots
    ]
