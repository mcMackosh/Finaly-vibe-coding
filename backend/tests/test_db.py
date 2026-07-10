"""Unit tests for the SQLite data layer."""

import json
import sqlite3

import pytest

from app import database as db


@pytest.fixture()
def db_file(tmp_path):
    """A freshly initialized database in a temp file."""
    path = tmp_path / "finally.db"
    db.init_db(path)
    return path


@pytest.fixture()
def conn(db_file):
    with db.db_conn(db_file) as c:
        yield c


# --- init / schema / seed --------------------------------------------------

def test_schema_creates_all_tables(conn):
    names = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {
        "users_profile",
        "watchlist",
        "positions",
        "trades",
        "portfolio_snapshots",
        "chat_messages",
    } <= names


def test_seed_user_profile(conn):
    profile = db.get_profile(conn)
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0
    assert profile["created_at"]


def test_seed_watchlist_has_ten_default_tickers(conn):
    tickers = [w["ticker"] for w in db.list_watchlist(conn)]
    assert tickers == [
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
        "NVDA", "META", "JPM", "V", "NFLX",
    ]


def test_init_db_is_idempotent(db_file):
    db.init_db(db_file)  # already initialized by fixture; second call must be safe
    db.init_db(db_file)
    with db.db_conn(db_file) as c:
        assert len(db.list_watchlist(c)) == 10
        assert db.get_profile(c)["cash_balance"] == 10000.0


# --- watchlist -------------------------------------------------------------

def test_watchlist_unique_constraint(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (db.new_id(), "default", "AAPL", db.now_iso()),
        )


def test_add_to_watchlist_is_idempotent(conn):
    first = db.add_to_watchlist(conn, "PYPL")
    second = db.add_to_watchlist(conn, "pypl")
    assert first["id"] == second["id"]
    tickers = [w["ticker"] for w in db.list_watchlist(conn)]
    assert tickers.count("PYPL") == 1


def test_remove_from_watchlist(conn):
    assert db.remove_from_watchlist(conn, "AAPL") is True
    assert db.remove_from_watchlist(conn, "AAPL") is False
    assert "AAPL" not in [w["ticker"] for w in db.list_watchlist(conn)]


# --- positions -------------------------------------------------------------

def test_upsert_position_inserts_then_updates(conn):
    created = db.upsert_position(conn, "AAPL", quantity=10, avg_cost=190.0)
    assert created["quantity"] == 10
    assert created["avg_cost"] == 190.0

    updated = db.upsert_position(conn, "AAPL", quantity=15, avg_cost=192.5)
    assert updated["quantity"] == 15
    assert updated["avg_cost"] == 192.5

    assert len(db.list_positions(conn)) == 1


def test_get_and_delete_position(conn):
    db.upsert_position(conn, "TSLA", quantity=3, avg_cost=250.0)
    assert db.get_position(conn, "TSLA")["quantity"] == 3
    assert db.delete_position(conn, "TSLA") is True
    assert db.get_position(conn, "TSLA") is None
    assert db.delete_position(conn, "TSLA") is False


def test_positions_unique_constraint(conn):
    db.upsert_position(conn, "NVDA", quantity=1, avg_cost=120.0)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (db.new_id(), "default", "NVDA", 2, 121.0, db.now_iso()),
        )


# --- trades ----------------------------------------------------------------

def test_add_and_list_trades(conn):
    db.add_trade(conn, "AAPL", side="buy", quantity=5, price=191.0)
    db.add_trade(conn, "AAPL", side="sell", quantity=2, price=195.0)
    trades = db.list_trades(conn)
    assert len(trades) == 2
    assert {t["side"] for t in trades} == {"buy", "sell"}


def test_trade_side_check_constraint(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (db.new_id(), "default", "AAPL", "hold", 1, 100.0, db.now_iso()),
        )


# --- portfolio_snapshots ---------------------------------------------------

def test_add_and_list_snapshots(conn):
    db.add_snapshot(conn, total_value=10000.0)
    db.add_snapshot(conn, total_value=10250.5)
    snaps = db.list_snapshots(conn)
    assert [s["total_value"] for s in snaps] == [10000.0, 10250.5]


# --- chat_messages ---------------------------------------------------------

def test_add_chat_message_user_has_null_actions(conn):
    msg = db.add_chat_message(conn, role="user", content="Hi")
    assert msg["actions"] is None
    assert msg["role"] == "user"


def test_add_chat_message_assistant_stores_actions_json(conn):
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}]}
    msg = db.add_chat_message(conn, role="assistant", content="Bought", actions=actions)
    assert json.loads(msg["actions"]) == actions


def test_chat_message_role_check_constraint(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (db.new_id(), "default", "system", "x", None, db.now_iso()),
        )


def test_list_chat_messages_limit_returns_recent_in_order(conn):
    for i in range(5):
        db.add_chat_message(conn, role="user", content=f"msg-{i}")
    recent = db.list_chat_messages(conn, limit=2)
    assert [m["content"] for m in recent] == ["msg-3", "msg-4"]


# --- transaction behavior --------------------------------------------------

def test_db_conn_rolls_back_on_error(db_file):
    with pytest.raises(RuntimeError):
        with db.db_conn(db_file) as c:
            db.upsert_position(c, "AAPL", quantity=99, avg_cost=1.0)
            raise RuntimeError("boom")
    with db.db_conn(db_file) as c:
        assert db.get_position(c, "AAPL") is None
