"""
Database schema, connection management, and row normalization.

Exported functions maintain the same signatures as the original journal_db.py
for backwards compatibility. Internal callers should import from here directly.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

DB_PATH = os.getenv("JOURNAL_DB_PATH", "data/journal.db")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _normalize_session_name(session: Optional[str]) -> str:
    if not session:
        return "Unknown"
    normalized = str(session).strip().upper().replace("-", "_").replace(" ", "_")
    mapping = {
        "ASIAN": "Asian",
        "LONDON": "London",
        "NY": "NY",
        "NEW_YORK": "NY",
        "UNKNOWN": "Unknown",
    }
    return mapping.get(normalized, str(session))


def compute_rr_ratio(
    entry_price: Any,
    sl_price: Any,
    tp_price: Any,
) -> Optional[float]:
    entry = _safe_float(entry_price)
    sl = _safe_float(sl_price)
    tp = _safe_float(tp_price)
    if entry is None or sl is None or tp is None:
        return None
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk <= 0 or reward < 0:
        return None
    return reward / risk


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _normalize_trade_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Return a trade row with both legacy and v2 field aliases."""
    from bot.session_detector import detect_session

    trade = dict(row)

    entry_price = trade.get("entry_price", trade.get("entry"))
    sl_price = trade.get("sl_price", trade.get("sl"))
    tp_price = trade.get("tp_price", trade.get("tp"))
    position_size = trade.get("position_size")
    if position_size is None:
        position_size = trade.get("lot_size", trade.get("risk_amount", 0))

    trade["entry_price"] = entry_price
    trade["sl_price"] = sl_price
    trade["tp_price"] = tp_price
    trade["position_size"] = position_size

    trade["external_id"] = trade.get("external_id", trade.get("external_trade_id"))
    trade["provider"] = trade.get("provider", trade.get("source"))
    trade["account_id"] = trade.get("account_id", 1)
    trade["session"] = _normalize_session_name(trade.get("session") or detect_session(trade.get("ts_open", "")))
    trade["rr_ratio"] = trade.get("rr_ratio")
    if trade["rr_ratio"] is None:
        trade["rr_ratio"] = compute_rr_ratio(
            trade.get("entry_price", trade.get("entry")),
            trade.get("sl_price", trade.get("sl")),
            trade.get("tp_price", trade.get("tp")),
        )

    if "indicator_data" in trade and trade["indicator_data"]:
        try:
            if isinstance(trade["indicator_data"], str):
                trade["indicator_data"] = json.loads(trade["indicator_data"])
        except Exception:
            trade["indicator_data"] = {}

    return trade


# ── Schema initialization ────────────────────────────────────────────────────


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    # Accounts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            initial_balance REAL NOT NULL,
            max_daily_loss_pct REAL DEFAULT 5.0,
            max_total_loss_pct REAL DEFAULT 10.0,
            profit_target_pct REAL DEFAULT 10.0,
            risk_per_trade_pct REAL DEFAULT 1.0,
            firm_name TEXT,
            broker TEXT,
            platform TEXT,
            rule_template TEXT,
            consistency_pct REAL,
            min_trading_days INTEGER,
            min_profitable_days INTEGER,
            profitable_day_threshold_pct REAL,
            static_drawdown_floor REAL,
            inactivity_limit_days INTEGER,
            payout_frequency_days INTEGER,
            timezone_name TEXT DEFAULT 'UTC',
            timezone TEXT DEFAULT 'UTC',
            current_balance REAL DEFAULT 10000,
            status TEXT DEFAULT 'ACTIVE',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            asset_type TEXT DEFAULT 'forex',
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            position_size REAL NOT NULL,
            sl_price REAL,
            tp_price REAL,
            exit_price REAL,
            pnl_usd REAL,
            pnl_pct REAL,
            commission REAL DEFAULT 0,
            swap REAL DEFAULT 0,
            outcome TEXT DEFAULT 'OPEN',
            ts_open TEXT NOT NULL,
            ts_close TEXT,
            session TEXT,
            timeframe TEXT,
            strategy TEXT,
            notes TEXT,
            external_id TEXT,
            provider TEXT,
            is_perfect INTEGER DEFAULT 0,
            week_start TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Trade events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_ts TEXT NOT NULL,
            provider TEXT,
            payload TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trade_id) REFERENCES trades(id)
        )
    """)

    # Trade reviews table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL UNIQUE,
            reviewer_note TEXT,
            should_have_done_entry TEXT,
            should_have_done_exit TEXT,
            should_have_done_sl TEXT,
            should_have_done_tp TEXT,
            week_start TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trade_id) REFERENCES trades(id)
        )
    """)

    # Weekly reviews table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weekly_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            summary TEXT,
            key_wins TEXT,
            key_mistakes TEXT,
            next_week_focus TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, week_start),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Weekly goals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weekly_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            goal_type TEXT NOT NULL,
            target_value REAL,
            target_label TEXT,
            plan_outline TEXT,
            status TEXT DEFAULT 'ACTIVE',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Drawings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drawings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            drawing_type TEXT NOT NULL,
            drawing_data TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trade_id) REFERENCES trades(id)
        )
    """)

    # Pine webhook events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pine_webhook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT NOT NULL UNIQUE,
            payload TEXT NOT NULL,
            processed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Monte Carlo simulations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monte_carlo_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            num_simulations INTEGER NOT NULL,
            num_trades INTEGER NOT NULL,
            initial_balance REAL NOT NULL,
            results TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Migrations for missing columns
    trade_cols = _table_columns(conn, "trades")
    if "is_perfect" not in trade_cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN is_perfect INTEGER DEFAULT 0")
    if "week_start" not in trade_cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN week_start TEXT")
    if "indicator_data" not in trade_cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN indicator_data TEXT")
    if "direction_correct" not in trade_cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN direction_correct INTEGER DEFAULT NULL")
    if "rr_ratio" not in trade_cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN rr_ratio REAL")
    if "session" not in trade_cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN session TEXT")
    if "external_id" not in trade_cols and "external_trade_id" not in trade_cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN external_id TEXT")
        trade_cols.add("external_id")
    elif "external_id" not in trade_cols and "external_trade_id" in trade_cols:
        trade_cols.add("external_trade_id")
    if "provider" not in trade_cols and "source" not in trade_cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN provider TEXT")
        trade_cols.add("provider")

    account_cols = _table_columns(conn, "accounts")
    if "rule_template" not in account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN rule_template TEXT")
    if "consistency_pct" not in account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN consistency_pct REAL")
    if "min_trading_days" not in account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN min_trading_days INTEGER")
    if "min_profitable_days" not in account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN min_profitable_days INTEGER")
    if "profitable_day_threshold_pct" not in account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN profitable_day_threshold_pct REAL")
    if "static_drawdown_floor" not in account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN static_drawdown_floor REAL")
    if "inactivity_limit_days" not in account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN inactivity_limit_days INTEGER")
    if "payout_frequency_days" not in account_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN payout_frequency_days INTEGER")

    conn.commit()
    conn.close()
