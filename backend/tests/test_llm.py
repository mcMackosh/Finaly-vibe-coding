"""Unit tests for the LLM chat integration module."""

import pytest

from app import llm
from app.llm import (
    build_system_prompt,
    call_llm,
    execute_llm_actions,
    parse_llm_content,
    run_chat,
)
from app.models import LlmResponse, PortfolioOut, TradeAction, WatchlistChange


# --------------------------------------------------------------------------- #
# Structured output parsing
# --------------------------------------------------------------------------- #
def test_parse_valid_json():
    content = '{"message": "hi", "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}]}'
    resp = parse_llm_content(content)
    assert resp.message == "hi"
    assert resp.trades == [TradeAction(ticker="AAPL", side="buy", quantity=5)]
    assert resp.watchlist_changes == []


def test_parse_json_wrapped_in_prose():
    content = 'Sure! Here you go:\n```json\n{"message": "ok"}\n```\nHope that helps.'
    resp = parse_llm_content(content)
    assert resp.message == "ok"


def test_parse_partial_data_defaults_lists():
    resp = parse_llm_content('{"message": "just text"}')
    assert resp.message == "just text"
    assert resp.trades == []
    assert resp.watchlist_changes == []


def test_parse_invalid_json_raises():
    with pytest.raises(ValueError):
        parse_llm_content("not json at all")


def test_parse_missing_required_field_raises():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        parse_llm_content('{"trades": []}')  # no message


def test_parse_invalid_side_raises():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        parse_llm_content('{"message": "x", "trades": [{"ticker": "A", "side": "hold", "quantity": 1}]}')


def test_parse_zero_quantity_raises():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        parse_llm_content('{"message": "x", "trades": [{"ticker": "A", "side": "buy", "quantity": 0}]}')


# --------------------------------------------------------------------------- #
# Mock mode
# --------------------------------------------------------------------------- #
async def test_mock_mode_returns_deterministic(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    resp = await call_llm("how am I doing?", {}, [])
    assert resp == await call_llm("how am I doing?", {}, [])
    assert "how am I doing?" in resp.message
    assert resp.trades == []


async def test_mock_mode_emits_trade_on_keyword(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    resp = await call_llm("please buy 5 AAPL now", {}, [])
    assert resp.trades == [TradeAction(ticker="AAPL", side="buy", quantity=5)]


async def test_mock_mode_accepts_portfolio_model(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    ctx = PortfolioOut(cash_balance=10000.0, total_value=10000.0, positions=[])
    resp = await call_llm("sell 2.5 TSLA", ctx, [{"role": "user", "content": "hi"}])
    assert resp.trades == [TradeAction(ticker="TSLA", side="sell", quantity=2.5)]


async def test_mock_env_absent_is_not_mock(monkeypatch):
    monkeypatch.delenv("LLM_MOCK", raising=False)
    assert llm._is_mock() is False
    monkeypatch.setenv("LLM_MOCK", "false")
    assert llm._is_mock() is False


# --------------------------------------------------------------------------- #
# System prompt
# --------------------------------------------------------------------------- #
def test_system_prompt_includes_context_dict():
    ctx = {
        "cash_balance": 8500.0,
        "total_value": 12345.0,
        "positions": [
            {"ticker": "AAPL", "quantity": 10, "avg_cost": 190, "current_price": 200, "unrealized_pnl": 100}
        ],
        "watchlist": [{"ticker": "TSLA"}, {"ticker": "NVDA"}],
    }
    prompt = build_system_prompt(ctx)
    assert "FinAlly" in prompt
    assert "8500.0" in prompt
    assert "12345.0" in prompt
    assert "AAPL" in prompt
    assert "TSLA" in prompt and "NVDA" in prompt


def test_system_prompt_accepts_portfolio_model():
    ctx = PortfolioOut(cash_balance=10000.0, total_value=10000.0, positions=[])
    prompt = build_system_prompt(ctx)
    assert "FinAlly" in prompt
    assert "no open positions" in prompt
    assert "(empty)" in prompt


def test_system_prompt_handles_empty_portfolio():
    prompt = build_system_prompt({"cash_balance": 10000.0})
    assert "no open positions" in prompt
    assert "(empty)" in prompt


# --------------------------------------------------------------------------- #
# Auto-execution of actions
# --------------------------------------------------------------------------- #
async def test_execute_actions_success():
    async def execute_trade(ticker, side, quantity):
        return {"ticker": ticker, "side": side, "quantity": quantity, "price": 200.0}

    async def modify_watchlist(ticker, action):
        pass

    resp = LlmResponse(
        message="done",
        trades=[TradeAction(ticker="AAPL", side="buy", quantity=5)],
        watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
    )
    result = await execute_llm_actions(resp, execute_trade=execute_trade, modify_watchlist=modify_watchlist)

    assert len(result["trades_executed"]) == 1
    assert result["trades_executed"][0]["price"] == 200.0
    assert result["watchlist_changes_made"] == [{"ticker": "PYPL", "action": "add"}]
    assert result["errors"] == []


async def test_execute_actions_insufficient_cash_becomes_error():
    async def execute_trade(ticker, side, quantity):
        raise ValueError("Insufficient cash for buy: needed $5000, had $200")

    async def modify_watchlist(ticker, action):
        pass

    resp = LlmResponse(message="x", trades=[TradeAction(ticker="AAPL", side="buy", quantity=100)])
    result = await execute_llm_actions(resp, execute_trade=execute_trade, modify_watchlist=modify_watchlist)

    assert result["trades_executed"] == []
    assert "Insufficient cash" in result["errors"][0]


async def test_execute_actions_partial_failure_isolated():
    async def execute_trade(ticker, side, quantity):
        if ticker == "BAD":
            raise ValueError("nope")
        return {"ticker": ticker, "filled": True}

    async def modify_watchlist(ticker, action):
        pass

    resp = LlmResponse(
        message="x",
        trades=[
            TradeAction(ticker="AAPL", side="buy", quantity=1),
            TradeAction(ticker="BAD", side="buy", quantity=1),
        ],
    )
    result = await execute_llm_actions(resp, execute_trade=execute_trade, modify_watchlist=modify_watchlist)

    assert len(result["trades_executed"]) == 1
    assert len(result["errors"]) == 1


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
async def test_run_chat_wires_everything(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    executed = []

    async def load_ctx():
        return {"cash_balance": 10000.0}

    async def load_history():
        return [{"role": "user", "content": "earlier"}]

    async def execute_trade(ticker, side, quantity):
        executed.append((ticker, side, quantity))
        return {"ticker": ticker}

    async def modify_watchlist(ticker, action):
        pass

    resp, actions = await run_chat(
        "buy 3 NVDA",
        load_portfolio_context=load_ctx,
        load_history=load_history,
        execute_trade=execute_trade,
        modify_watchlist=modify_watchlist,
    )
    assert resp.trades[0].ticker == "NVDA"
    assert executed == [("NVDA", "buy", 3.0)]
    assert len(actions["trades_executed"]) == 1
