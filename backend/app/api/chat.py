"""Chat REST endpoints (PLAN.md §8, §9).

POST /api/chat runs one full turn through the LLM layer's injected orchestrator:
it loads portfolio context + history, calls the model, and auto-executes any trades /
watchlist changes the model returns — reusing the same trade path as manual trades.
"""

from fastapi import APIRouter, Request

from app.database import (
    add_chat_message,
    add_to_watchlist,
    db_conn,
    list_chat_messages,
    list_watchlist,
    remove_from_watchlist,
)
from app.llm import run_chat
from app.models import ChatActionsOut, ChatMessageOut, ChatRequest, ChatResponse
from app.trading import build_portfolio, execute_trade

router = APIRouter(prefix="/api/chat")

HISTORY_LIMIT = 20


@router.get("/history")
async def get_chat_history(request: Request) -> list[ChatMessageOut]:
    with db_conn() as conn:
        messages = list_chat_messages(conn, limit=HISTORY_LIMIT)
    return [
        ChatMessageOut(
            id=m["id"],
            role=m["role"],
            content=m["content"],
            actions=_parse_actions(m["actions"]),
            created_at=m["created_at"],
        )
        for m in messages
    ]


@router.post("")
async def post_chat(request: Request, body: ChatRequest) -> ChatResponse:
    cache = request.app.state.price_cache
    provider = request.app.state.market_data_provider

    async def load_portfolio_context() -> dict:
        with db_conn() as conn:
            portfolio = await build_portfolio(conn, cache)
            watchlist = list_watchlist(conn)
        return {
            "cash_balance": portfolio.cash_balance,
            "total_value": portfolio.total_value,
            "positions": [p.model_dump() for p in portfolio.positions],
            "watchlist": [{"ticker": w["ticker"]} for w in watchlist],
        }

    async def load_history() -> list[dict]:
        with db_conn() as conn:
            messages = list_chat_messages(conn, limit=HISTORY_LIMIT)
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    async def do_execute_trade(ticker: str, side: str, quantity: float) -> dict:
        with db_conn() as conn:
            return await execute_trade(conn, cache, ticker, quantity, side)

    async def do_modify_watchlist(ticker: str, action: str) -> None:
        ticker = ticker.upper()
        with db_conn() as conn:
            if action == "add":
                add_to_watchlist(conn, ticker)
            else:
                remove_from_watchlist(conn, ticker)
        if action == "add":
            await provider.add_ticker(ticker)
        else:
            await provider.remove_ticker(ticker)

    response, actions = await run_chat(
        body.message,
        load_portfolio_context=load_portfolio_context,
        load_history=load_history,
        execute_trade=do_execute_trade,
        modify_watchlist=do_modify_watchlist,
    )

    actions_out = ChatActionsOut(
        trades=actions["trades_executed"],
        watchlist_changes=actions["watchlist_changes_made"],
        error="; ".join(actions["errors"]) if actions["errors"] else None,
    )

    with db_conn() as conn:
        add_chat_message(conn, "user", body.message)
        add_chat_message(conn, "assistant", response.message, actions=actions_out.model_dump())

    return ChatResponse(message=response.message, actions=actions_out)


def _parse_actions(raw: str | None) -> dict | None:
    if not raw:
        return None
    import json

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
