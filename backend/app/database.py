"""SQLite data layer: lazy schema init, connection helpers, and CRUD functions.

The database is a single file (default: ``<project-root>/db/finally.db``) that the
backend initializes on first use — creating the schema and seeding default data if
the file is missing or empty. Override the location with the ``FINALLY_DB_PATH``
environment variable (e.g. ``/app/db/finally.db`` inside the container).

CRUD helpers take an open connection as their first argument so callers can group
several writes into one atomic transaction (e.g. a trade updates ``trades``,
``positions``, ``users_profile``, and ``portfolio_snapshots`` together). Use the
``db_conn()`` context manager to obtain a connection that commits on success and
rolls back on error.
"""

import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
_SEED_PATH = Path(__file__).resolve().parent.parent / "db" / "seed.sql"
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "finally.db"

DEFAULT_USER_ID = "default"


def db_path() -> Path:
    """Resolve the SQLite file path from ``FINALLY_DB_PATH`` or the default location."""
    override = os.environ.get("FINALLY_DB_PATH")
    return Path(override) if override else _DEFAULT_DB_PATH


def now_iso() -> str:
    """UTC timestamp in the Z-suffixed ISO-8601 format used across the schema."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    return str(uuid.uuid4())


def get_connection(path: Path | None = None) -> sqlite3.Connection:
    """Open a configured connection. Caller owns closing it."""
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_conn(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Connection context manager: commits on success, rolls back on error."""
    conn = get_connection(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _tables_exist(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users_profile'"
    ).fetchone()
    return row is not None


def _is_seeded(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT COUNT(*) AS n FROM users_profile").fetchone()
    return row["n"] > 0


def init_db(path: Path | None = None) -> None:
    """Create the schema and seed default data if absent. Idempotent."""
    with db_conn(path) as conn:
        if not _tables_exist(conn):
            conn.executescript(_SCHEMA_PATH.read_text())
        if not _is_seeded(conn):
            conn.executescript(_SEED_PATH.read_text())


# --- users_profile ---------------------------------------------------------

def get_profile(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> dict | None:
    row = conn.execute(
        "SELECT * FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def update_cash_balance(
    conn: sqlite3.Connection, cash_balance: float, user_id: str = DEFAULT_USER_ID
) -> None:
    conn.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (cash_balance, user_id),
    )


# --- watchlist -------------------------------------------------------------

def list_watchlist(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_to_watchlist(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> dict:
    """Add a ticker (idempotent). Returns the existing or newly created row."""
    ticker = ticker.upper()
    conn.execute(
        "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (new_id(), user_id, ticker, now_iso()),
    )
    row = conn.execute(
        "SELECT * FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
    ).fetchone()
    return dict(row)


def remove_from_watchlist(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> bool:
    cur = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper()),
    )
    return cur.rowcount > 0


# --- positions -------------------------------------------------------------

def list_positions(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? ORDER BY ticker", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_position(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> dict | None:
    row = conn.execute(
        "SELECT * FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper()),
    ).fetchone()
    return dict(row) if row else None


def upsert_position(
    conn: sqlite3.Connection,
    ticker: str,
    quantity: float,
    avg_cost: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Insert or update the holding for a ticker. Returns the resulting row."""
    ticker = ticker.upper()
    conn.execute(
        """
        INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, ticker) DO UPDATE SET
            quantity = excluded.quantity,
            avg_cost = excluded.avg_cost,
            updated_at = excluded.updated_at
        """,
        (new_id(), user_id, ticker, quantity, avg_cost, now_iso()),
    )
    return get_position(conn, ticker, user_id)


def delete_position(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> bool:
    cur = conn.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper()),
    )
    return cur.rowcount > 0


# --- trades ----------------------------------------------------------------

def add_trade(
    conn: sqlite3.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    trade_id = new_id()
    conn.execute(
        """
        INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (trade_id, user_id, ticker.upper(), side, quantity, price, now_iso()),
    )
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    return dict(row)


def list_trades(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM trades WHERE user_id = ? ORDER BY executed_at, rowid", (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# --- portfolio_snapshots ---------------------------------------------------

def add_snapshot(
    conn: sqlite3.Connection, total_value: float, user_id: str = DEFAULT_USER_ID
) -> dict:
    snap_id = new_id()
    conn.execute(
        """
        INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
        VALUES (?, ?, ?, ?)
        """,
        (snap_id, user_id, total_value, now_iso()),
    )
    row = conn.execute(
        "SELECT * FROM portfolio_snapshots WHERE id = ?", (snap_id,)
    ).fetchone()
    return dict(row)


def list_snapshots(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM portfolio_snapshots WHERE user_id = ? ORDER BY recorded_at, rowid",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# --- chat_messages ---------------------------------------------------------

def add_chat_message(
    conn: sqlite3.Connection,
    role: str,
    content: str,
    actions: dict | list | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Append a chat message. ``actions`` is JSON-encoded (null for user messages)."""
    msg_id = new_id()
    actions_json = json.dumps(actions) if actions is not None else None
    conn.execute(
        """
        INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (msg_id, user_id, role, content, actions_json, now_iso()),
    )
    row = conn.execute(
        "SELECT * FROM chat_messages WHERE id = ?", (msg_id,)
    ).fetchone()
    return dict(row)


def list_chat_messages(
    conn: sqlite3.Connection, limit: int | None = None, user_id: str = DEFAULT_USER_ID
) -> list[dict]:
    """Return chat messages oldest-first. With ``limit``, returns the most recent N."""
    if limit is not None:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        rows = list(reversed(rows))
    else:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at, rowid",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]
