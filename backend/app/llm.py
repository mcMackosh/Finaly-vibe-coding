"""LLM chat integration for FinAlly.

Talks to OpenRouter (free-tier gpt-oss) over plain HTTPS, asks for a single JSON
object matching :class:`app.models.LlmResponse`, and parses it leniently.

Two entry points:
- :func:`call_llm` — produces just the structured response (pure model call).
- :func:`run_chat` — one full turn: load context + history, call the model, then
  auto-execute the returned trades / watchlist changes via injected ops. This keeps
  the module DB-agnostic; the chat route (``app/api/chat.py``) supplies the loaders
  and the trade / watchlist operations from ``app/trading.py`` and ``app/database.py``.
"""

import asyncio
import json
import logging
import os
import re
from typing import Awaitable, Callable

import httpx
from pydantic import BaseModel, ValidationError

from app.models import LlmResponse, TradeAction

# Injected operations (supplied by the chat route).
ExecuteTrade = Callable[[str, str, float], Awaitable[dict]]
ModifyWatchlist = Callable[[str, str], Awaitable[None]]

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"

_PARSE_FAIL_MESSAGE = "Sorry, I had trouble understanding that. Could you rephrase?"


# --------------------------------------------------------------------------- #
# Mock mode
# --------------------------------------------------------------------------- #
def _is_mock() -> bool:
    return os.environ.get("LLM_MOCK", "").lower() == "true"


_MOCK_TRADE_RE = re.compile(
    r"\b(buy|sell)\b\s+([0-9]+(?:\.[0-9]+)?)\s+([A-Za-z]{1,5})\b", re.IGNORECASE
)


def _mock_llm_response(user_message: str) -> LlmResponse:
    """Deterministic response for tests / offline dev.

    Echoes the message, and if it contains a ``buy N TICKER`` / ``sell N TICKER``
    phrase, emits the corresponding trade so E2E flows can assert on inline
    execution without a real model call.
    """
    match = _MOCK_TRADE_RE.search(user_message)
    if match:
        side, qty, ticker = match.group(1).lower(), float(match.group(2)), match.group(3).upper()
        return LlmResponse(
            message=f"Okay, placing a {side} order for {qty:g} {ticker}. (mock)",
            trades=[TradeAction(ticker=ticker, side=side, quantity=qty)],
        )
    return LlmResponse(message=f"You said: {user_message}. (This is a mock response.)")


# --------------------------------------------------------------------------- #
# Prompt construction
# --------------------------------------------------------------------------- #
_SCHEMA_HINT = (
    '{"message": "<text for the user>", '
    '"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}], '
    '"watchlist_changes": [{"ticker": "PYPL", "action": "add"}]}'
)


def _as_dict(context: BaseModel | dict) -> dict:
    """Normalize the portfolio context to a plain dict (accepts a pydantic model)."""
    return context.model_dump() if isinstance(context, BaseModel) else dict(context)


def build_system_prompt(context: BaseModel | dict) -> str:
    """Compose the system prompt including a snapshot of the portfolio."""
    ctx = _as_dict(context)
    cash = ctx.get("cash_balance", 0.0)
    total_value = ctx.get("total_value", cash)
    positions = ctx.get("positions", []) or []
    watchlist = ctx.get("watchlist", []) or []

    if positions:
        pos_lines = "\n".join(
            f"  - {p.get('ticker')}: qty={p.get('quantity')}, avg_cost=${p.get('avg_cost')}, "
            f"price=${p.get('current_price')}, P&L=${p.get('unrealized_pnl')}"
            for p in positions
        )
    else:
        pos_lines = "  (no open positions)"

    watch_line = ", ".join(
        w.get("ticker") if isinstance(w, dict) else str(w) for w in watchlist
    ) or "(empty)"

    return (
        "You are FinAlly, an AI trading assistant embedded in a simulated trading "
        "workstation. You help the user analyze and manage a virtual portfolio.\n\n"
        "Current portfolio:\n"
        f"  Cash: ${cash}\n"
        f"  Total portfolio value: ${total_value}\n"
        f"  Positions:\n{pos_lines}\n"
        f"  Watchlist: {watch_line}\n\n"
        "Guidelines:\n"
        "- Analyze portfolio composition, risk concentration, and P&L.\n"
        "- Suggest trades with brief, data-driven reasoning.\n"
        "- Execute trades when the user asks or agrees, via the `trades` field.\n"
        "- Manage the watchlist proactively via `watchlist_changes`.\n"
        "- Be concise. All money is simulated.\n\n"
        "You MUST reply with ONLY a single JSON object, no markdown fences and no "
        "extra prose, matching this shape:\n"
        f"{_SCHEMA_HINT}\n"
        "`trades` and `watchlist_changes` are optional and default to empty lists. "
        "Only include a trade or watchlist change when you actually intend to act."
    )


def _build_messages(
    context: BaseModel | dict, history: list[dict], user_message: str
) -> list[dict]:
    messages = [{"role": "system", "content": build_system_prompt(context)}]
    for turn in history:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #
def _extract_json_object(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            raise ValueError("no JSON object found in response")
        return json.loads(match.group(0))


def parse_llm_content(content: str) -> LlmResponse:
    """Parse and validate raw model content into an :class:`LlmResponse`."""
    data = _extract_json_object(content)
    return LlmResponse.model_validate(data)


# --------------------------------------------------------------------------- #
# The LLM call
# --------------------------------------------------------------------------- #
async def _call_openrouter(messages: list[dict], model: str, api_key: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "messages": messages},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def call_llm(
    user_message: str,
    context: BaseModel | dict,
    history: list[dict],
    *,
    retries: int = 3,
    backoff_s: float = 1.5,
) -> LlmResponse:
    """Produce a validated :class:`LlmResponse` for the user's chat message.

    ``context`` is the portfolio snapshot (a pydantic model such as ``PortfolioOut``
    or a plain dict) with cash, positions (incl. P&L), total value, and optionally
    a ``watchlist``. ``history`` is oldest->newest ``{"role", "content"}`` dicts.

    In mock mode returns a deterministic response. Otherwise calls OpenRouter,
    retrying the request/parse/validate cycle on transient failures. If every
    attempt fails, returns a graceful fallback message rather than raising, so the
    chat handler never has to deal with an exception from the model call.
    """
    if _is_mock():
        return _mock_llm_response(user_message)

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    messages = _build_messages(context, history, user_message)

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        if attempt > 0:
            await asyncio.sleep(backoff_s)
        try:
            content = await _call_openrouter(messages, model, api_key)
            return parse_llm_content(content)
        except (httpx.HTTPError, ValueError, ValidationError, KeyError) as err:
            last_error = err
            logger.warning("LLM attempt %d failed: %s", attempt + 1, err)

    logger.error("LLM call failed after %d attempts: %s", retries + 1, last_error)
    return LlmResponse(message=_PARSE_FAIL_MESSAGE)


# --------------------------------------------------------------------------- #
# Auto-execution of actions
# --------------------------------------------------------------------------- #
async def execute_llm_actions(
    response: LlmResponse,
    *,
    execute_trade: ExecuteTrade,
    modify_watchlist: ModifyWatchlist,
) -> dict:
    """Execute the trades and watchlist changes the model asked for.

    ``execute_trade(ticker, side, quantity)`` performs one trade and returns a
    result dict; it should raise on validation failure (insufficient cash/shares).
    ``modify_watchlist(ticker, action)`` adds/removes a ticker. Failures are
    collected into ``errors`` so the caller can relay them to the user.
    """
    results: dict = {"trades_executed": [], "watchlist_changes_made": [], "errors": []}

    for trade in response.trades:
        try:
            outcome = await execute_trade(trade.ticker, trade.side, trade.quantity)
            results["trades_executed"].append(outcome)
        except Exception as err:  # surfaced back into chat, not raised
            results["errors"].append(
                f"Trade failed ({trade.side} {trade.quantity:g} {trade.ticker}): {err}"
            )

    for change in response.watchlist_changes:
        try:
            await modify_watchlist(change.ticker, change.action)
            results["watchlist_changes_made"].append(
                {"ticker": change.ticker, "action": change.action}
            )
        except Exception as err:
            results["errors"].append(
                f"Watchlist change failed ({change.action} {change.ticker}): {err}"
            )

    return results


# --------------------------------------------------------------------------- #
# Orchestrator — used by POST /api/chat
# --------------------------------------------------------------------------- #
async def run_chat(
    user_message: str,
    *,
    load_portfolio_context: Callable[[], Awaitable[dict]],
    load_history: Callable[[], Awaitable[list[dict]]],
    execute_trade: ExecuteTrade,
    modify_watchlist: ModifyWatchlist,
) -> tuple[LlmResponse, dict]:
    """Full chat turn: load context + history, call the model, execute actions.

    The DB loaders and portfolio ops are injected so this stays DB-agnostic.
    Returns the model response and the execution results dict
    (``{"trades_executed", "watchlist_changes_made", "errors"}``).
    """
    context = await load_portfolio_context()
    history = await load_history()
    response = await call_llm(user_message, context, history)
    actions = await execute_llm_actions(
        response, execute_trade=execute_trade, modify_watchlist=modify_watchlist
    )
    return response, actions
