#!/usr/bin/env python3
"""
Trading Journal Database Operations
Handles all database interactions for the trading journal
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

DB_PATH = os.getenv("JOURNAL_DB_PATH", "data/journal.db")


def get_connection() -> sqlite3.Connection:
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database schema"""
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
            timezone_name TEXT DEFAULT 'UTC',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    
    conn.commit()
    conn.close()


# Account operations
def create_account(
    name: str,
    currency: str,
    initial_balance: float,
    max_daily_loss_pct: float = 5.0,
    max_total_loss_pct: float = 10.0,
    profit_target_pct: float = 10.0,
    risk_per_trade_pct: float = 1.0,
    firm_name: str = "",
    broker: str = "",
    platform: str = "",
    timezone_name: str = "UTC",
) -> int:
    """Create a new trading account"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO accounts (
            name, currency, initial_balance, max_daily_loss_pct,
            max_total_loss_pct, profit_target_pct, risk_per_trade_pct,
            firm_name, broker, platform, timezone_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name, currency, initial_balance, max_daily_loss_pct,
            max_total_loss_pct, profit_target_pct, risk_per_trade_pct,
            firm_name, broker, platform, timezone_name
        ),
    )
    account_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return account_id


def get_accounts() -> List[Dict[str, Any]]:
    """Get all trading accounts"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts ORDER BY created_at DESC")
    accounts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return accounts


def get_account(account_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific account"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_account_rules(
    account_id: int,
    max_daily_loss_pct: float,
    max_total_loss_pct: float,
    profit_target_pct: float,
    risk_per_trade_pct: float,
) -> None:
    """Update account risk rules"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE accounts
        SET max_daily_loss_pct = ?, max_total_loss_pct = ?,
            profit_target_pct = ?, risk_per_trade_pct = ?
        WHERE id = ?
        """,
        (max_daily_loss_pct, max_total_loss_pct, profit_target_pct, risk_per_trade_pct, account_id),
    )
    conn.commit()
    conn.close()


# Trade operations
def create_trade(
    account_id: int,
    symbol: str,
    direction: str,
    entry_price: float,
    position_size: float,
    ts_open: str,
    asset_type: str = "forex",
    sl_price: Optional[float] = None,
    tp_price: Optional[float] = None,
    session: Optional[str] = None,
    timeframe: Optional[str] = None,
    strategy: Optional[str] = None,
    notes: Optional[str] = None,
    external_id: Optional[str] = None,
    provider: Optional[str] = None,
) -> int:
    """Create a new trade"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO trades (
            account_id, symbol, asset_type, direction, entry_price,
            position_size, sl_price, tp_price, ts_open, session,
            timeframe, strategy, notes, external_id, provider
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            account_id, symbol, asset_type, direction, entry_price,
            position_size, sl_price, tp_price, ts_open, session,
            timeframe, strategy, notes, external_id, provider
        ),
    )
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trade_id


def get_trade(trade_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific trade"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_trades(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get all trades with optional filters"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM trades WHERE 1=1"
    params = []
    
    if account_id is not None:
        query += " AND account_id = ?"
        params.append(account_id)
    
    if from_ts:
        query += " AND ts_open >= ?"
        params.append(from_ts)
    
    if to_ts:
        query += " AND ts_open <= ?"
        params.append(to_ts)
    
    query += " ORDER BY ts_open DESC"
    
    cursor.execute(query, params)
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return trades


def get_open_trades(account_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get all open trades"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM trades WHERE outcome = 'OPEN'"
    params = []
    
    if account_id is not None:
        query += " AND account_id = ?"
        params.append(account_id)
    
    query += " ORDER BY ts_open DESC"
    
    cursor.execute(query, params)
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return trades


def close_trade(
    trade_id: int,
    exit_price: float,
    outcome: str,
    event_type: str,
    provider: str,
    payload: Dict[str, Any],
    ts_close: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Close a trade and calculate P&L"""
    if ts_close is None:
        ts_close = datetime.now(timezone.utc).isoformat()
    
    trade = get_trade(trade_id)
    if not trade or trade["outcome"] != "OPEN":
        return None
    
    # Calculate P&L
    entry_price = trade["entry_price"]
    position_size = trade["position_size"]
    direction = trade["direction"]
    
    if direction == "LONG":
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    else:  # SHORT
        pnl_pct = ((entry_price - exit_price) / entry_price) * 100
    
    pnl_usd = (pnl_pct / 100) * position_size
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        UPDATE trades
        SET exit_price = ?, pnl_usd = ?, pnl_pct = ?, outcome = ?,
            ts_close = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (exit_price, pnl_usd, pnl_pct, outcome, ts_close, trade_id),
    )
    
    # Log event
    import json
    cursor.execute(
        """
        INSERT INTO trade_events (trade_id, event_type, event_ts, provider, payload)
        VALUES (?, ?, ?, ?, ?)
        """,
        (trade_id, event_type, ts_close, provider, json.dumps(payload)),
    )
    
    conn.commit()
    conn.close()
    
    return get_trade(trade_id)


def update_trade_sl_tp(trade_id: int, sl_price: Optional[float], tp_price: Optional[float]) -> None:
    """Update trade SL/TP levels"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE trades
        SET sl_price = ?, tp_price = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (sl_price, tp_price, trade_id),
    )
    conn.commit()
    conn.close()


def get_trade_events(trade_id: int) -> List[Dict[str, Any]]:
    """Get all events for a trade"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trade_events WHERE trade_id = ? ORDER BY event_ts DESC",
        (trade_id,)
    )
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events


# Statistics operations
def get_stats(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    """Calculate trading statistics"""
    trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    closed_trades = [t for t in trades if t["outcome"] != "OPEN"]
    
    if not closed_trades:
        account = get_account(account_id) if account_id else get_accounts()[0] if get_accounts() else None
        initial_balance = account["initial_balance"] if account else 0
        return {
            "total_trades": 0,
            "win_rate": 0,
            "total_pnl_usd": 0,
            "avg_win_usd": 0,
            "avg_loss_usd": 0,
            "profit_factor": 0,
            "max_drawdown_pct": 0,
            "sharpe_ratio": 0,
            "avg_rr": 0,
            "initial_balance": initial_balance,
        }
    
    wins = [t for t in closed_trades if (t.get("pnl_usd") or 0) > 0]
    losses = [t for t in closed_trades if (t.get("pnl_usd") or 0) < 0]
    
    total_pnl = sum(t.get("pnl_usd", 0) for t in closed_trades)
    total_wins = sum(t.get("pnl_usd", 0) for t in wins)
    total_losses = abs(sum(t.get("pnl_usd", 0) for t in losses))
    
    win_rate = (len(wins) / len(closed_trades)) * 100 if closed_trades else 0
    avg_win = total_wins / len(wins) if wins else 0
    avg_loss = total_losses / len(losses) if losses else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else 0
    
    # Calculate max drawdown
    balance = 0
    peak = 0
    max_dd = 0
    for t in sorted(closed_trades, key=lambda x: x.get("ts_close", "")):
        balance += t.get("pnl_usd", 0)
        if balance > peak:
            peak = balance
        dd = ((peak - balance) / peak * 100) if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    
    account = get_account(account_id) if account_id else get_accounts()[0] if get_accounts() else None
    initial_balance = account["initial_balance"] if account else 0
    
    return {
        "total_trades": len(closed_trades),
        "win_rate": win_rate,
        "total_pnl_usd": total_pnl,
        "avg_win_usd": avg_win,
        "avg_loss_usd": avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": 0,  # Placeholder
        "avg_rr": avg_win / avg_loss if avg_loss > 0 else 0,
        "initial_balance": initial_balance,
    }


def get_analytics_breakdown(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    """Get directional analytics breakdown"""
    trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    closed_trades = [t for t in trades if t["outcome"] != "OPEN"]
    
    long_trades = [t for t in closed_trades if t["direction"] == "LONG"]
    short_trades = [t for t in closed_trades if t["direction"] == "SHORT"]
    
    def calc_direction_stats(direction_trades):
        if not direction_trades:
            return {"count": 0, "win_rate": 0, "total_pnl": 0, "avg_pnl": 0}
        
        wins = [t for t in direction_trades if (t.get("pnl_usd") or 0) > 0]
        total_pnl = sum(t.get("pnl_usd", 0) for t in direction_trades)
        
        return {
            "count": len(direction_trades),
            "win_rate": (len(wins) / len(direction_trades)) * 100,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / len(direction_trades),
        }
    
    return {
        "long": calc_direction_stats(long_trades),
        "short": calc_direction_stats(short_trades),
    }


# Review operations
def upsert_trade_review_note(
    trade_id: int,
    reviewer_note: Optional[str] = None,
    should_have_done_entry: Optional[str] = None,
    should_have_done_exit: Optional[str] = None,
    should_have_done_sl: Optional[str] = None,
    should_have_done_tp: Optional[str] = None,
    week_start: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update trade review"""
    trade = get_trade(trade_id)
    if not trade:
        raise ValueError(f"Trade {trade_id} not found")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM trade_reviews WHERE trade_id = ?", (trade_id,))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute(
            """
            UPDATE trade_reviews
            SET reviewer_note = ?, should_have_done_entry = ?,
                should_have_done_exit = ?, should_have_done_sl = ?,
                should_have_done_tp = ?, week_start = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE trade_id = ?
            """,
            (
                reviewer_note, should_have_done_entry, should_have_done_exit,
                should_have_done_sl, should_have_done_tp, week_start, trade_id
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO trade_reviews (
                trade_id, reviewer_note, should_have_done_entry,
                should_have_done_exit, should_have_done_sl,
                should_have_done_tp, week_start
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id, reviewer_note, should_have_done_entry,
                should_have_done_exit, should_have_done_sl,
                should_have_done_tp, week_start
            ),
        )
    
    conn.commit()
    cursor.execute("SELECT * FROM trade_reviews WHERE trade_id = ?", (trade_id,))
    review = dict(cursor.fetchone())
    conn.close()
    return review


def get_weekly_review(account_id: int, week_start: str) -> Dict[str, Any]:
    """Get weekly review"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM weekly_reviews WHERE account_id = ? AND week_start = ?",
        (account_id, week_start)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return {
        "account_id": account_id,
        "week_start": week_start,
        "summary": None,
        "key_wins": None,
        "key_mistakes": None,
        "next_week_focus": None,
    }


def upsert_weekly_review(
    account_id: int,
    week_start: str,
    summary: Optional[str] = None,
    key_wins: Optional[str] = None,
    key_mistakes: Optional[str] = None,
    next_week_focus: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or update weekly review"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id FROM weekly_reviews WHERE account_id = ? AND week_start = ?",
        (account_id, week_start)
    )
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute(
            """
            UPDATE weekly_reviews
            SET summary = ?, key_wins = ?, key_mistakes = ?,
                next_week_focus = ?, updated_at = CURRENT_TIMESTAMP
            WHERE account_id = ? AND week_start = ?
            """,
            (summary, key_wins, key_mistakes, next_week_focus, account_id, week_start),
        )
    else:
        cursor.execute(
            """
            INSERT INTO weekly_reviews (
                account_id, week_start, summary, key_wins,
                key_mistakes, next_week_focus
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (account_id, week_start, summary, key_wins, key_mistakes, next_week_focus),
        )
    
    conn.commit()
    cursor.execute(
        "SELECT * FROM weekly_reviews WHERE account_id = ? AND week_start = ?",
        (account_id, week_start)
    )
    review = dict(cursor.fetchone())
    conn.close()
    return review


def get_weekly_goals(account_id: int, week_start: str) -> List[Dict[str, Any]]:
    """Get weekly goals"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM weekly_goals WHERE account_id = ? AND week_start = ? ORDER BY created_at",
        (account_id, week_start)
    )
    goals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return goals


def upsert_weekly_goal(
    account_id: int,
    week_start: str,
    goal_type: str,
    target_value: Optional[float] = None,
    target_label: Optional[str] = None,
    plan_outline: Optional[str] = None,
    status: str = "ACTIVE",
) -> Dict[str, Any]:
    """Create or update weekly goal"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT id FROM weekly_goals
        WHERE account_id = ? AND week_start = ? AND goal_type = ?
        """,
        (account_id, week_start, goal_type)
    )
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute(
            """
            UPDATE weekly_goals
            SET target_value = ?, target_label = ?, plan_outline = ?,
                status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (target_value, target_label, plan_outline, status, existing[0]),
        )
        goal_id = existing[0]
    else:
        cursor.execute(
            """
            INSERT INTO weekly_goals (
                account_id, week_start, goal_type, target_value,
                target_label, plan_outline, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (account_id, week_start, goal_type, target_value, target_label, plan_outline, status),
        )
        goal_id = cursor.lastrowid
    
    conn.commit()
    cursor.execute("SELECT * FROM weekly_goals WHERE id = ?", (goal_id,))
    goal = dict(cursor.fetchone())
    conn.close()
    return goal


# Drawing operations
def save_drawing(trade_id: int, drawing_type: str, drawing_data: str) -> int:
    """Save a drawing for a trade"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO drawings (trade_id, drawing_type, drawing_data) VALUES (?, ?, ?)",
        (trade_id, drawing_type, drawing_data)
    )
    drawing_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return drawing_id


def get_drawings_for_trade(trade_id: int) -> List[Dict[str, Any]]:
    """Get all drawings for a trade"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM drawings WHERE trade_id = ? ORDER BY created_at",
        (trade_id,)
    )
    drawings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return drawings


# Monte Carlo operations
def save_monte_carlo_run(
    account_id: int,
    num_simulations: int,
    num_trades: int,
    initial_balance: float,
    results: str,
) -> int:
    """Save Monte Carlo simulation results"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO monte_carlo_runs (
            account_id, num_simulations, num_trades, initial_balance, results
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (account_id, num_simulations, num_trades, initial_balance, results)
    )
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return run_id


def get_monte_carlo_stats(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    """Get Monte Carlo statistics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM monte_carlo_runs WHERE 1=1"
    params = []
    
    if account_id is not None:
        query += " AND account_id = ?"
        params.append(account_id)
    
    query += " ORDER BY created_at DESC LIMIT 1"
    
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    
    if row:
        import json
        result = dict(row)
        result["results"] = json.loads(result["results"])
        return result
    
    return {
        "num_simulations": 0,
        "num_trades": 0,
        "initial_balance": 0,
        "results": {},
    }


# Pine webhook operations
def record_pine_webhook(idempotency_key: str, payload: str) -> bool:
    """Record a Pine webhook event (idempotent)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO pine_webhook_events (idempotency_key, payload) VALUES (?, ?)",
            (idempotency_key, payload)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def find_trade_by_external_id(external_id: str, provider: str) -> Optional[Dict[str, Any]]:
    """Find a trade by external ID and provider"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trades WHERE external_id = ? AND provider = ?",
        (external_id, provider)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def find_open_trade_by_symbol(account_id: int, symbol: str) -> Optional[Dict[str, Any]]:
    """Find an open trade by symbol"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM trades
        WHERE account_id = ? AND symbol = ? AND outcome = 'OPEN'
        ORDER BY ts_open DESC LIMIT 1
        """,
        (account_id, symbol)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
