#!/usr/bin/env python3
"""
Trading Journal Database Operations
Handles all database interactions for the trading journal
"""
import os
import sqlite3
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

DB_PATH = os.getenv("JOURNAL_DB_PATH", "data/journal.db")


def get_connection() -> sqlite3.Connection:
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _normalize_trade_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Return a trade row with both legacy and v2 field aliases."""
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

    trade["entry"] = trade.get("entry", entry_price)
    trade["sl"] = trade.get("sl", sl_price)
    trade["tp"] = trade.get("tp", tp_price)

    trade["external_id"] = trade.get("external_id", trade.get("external_trade_id"))
    trade["provider"] = trade.get("provider", trade.get("source"))
    trade["account_id"] = trade.get("account_id", 1)
    return trade


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
    trade_columns = _table_columns(conn, "trades")
    row = {
        "account_id": account_id,
        "symbol": symbol,
        "asset_type": asset_type,
        "direction": direction,
        "entry_price": entry_price,
        "entry": entry_price,
        "position_size": position_size,
        "lot_size": position_size,
        "sl_price": sl_price if sl_price is not None else entry_price,
        "sl": sl_price if sl_price is not None else entry_price,
        "tp_price": tp_price if tp_price is not None else entry_price,
        "tp": tp_price if tp_price is not None else entry_price,
        "ts_open": ts_open,
        "session": session,
        "timeframe": timeframe,
        "strategy": strategy,
        "notes": notes,
        "external_id": external_id,
        "external_trade_id": external_id,
        "provider": provider,
        "source": provider or "manual_bot",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    insert_cols = [col for col in row.keys() if col in trade_columns and row[col] is not None]
    placeholders = ", ".join(["?"] * len(insert_cols))
    sql = f"INSERT INTO trades ({', '.join(insert_cols)}) VALUES ({placeholders})"
    cursor.execute(sql, [row[col] for col in insert_cols])
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
    return _normalize_trade_row(dict(row)) if row else None


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
    trades = [_normalize_trade_row(dict(row)) for row in cursor.fetchall()]
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
    trades = [_normalize_trade_row(dict(row)) for row in cursor.fetchall()]
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
    pnl_usd_override: Optional[float] = None,
    pnl_pct_override: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Close a trade and calculate P&L"""
    if ts_close is None:
        ts_close = datetime.now(timezone.utc).isoformat()
    
    trade = get_trade(trade_id)
    if not trade or trade["outcome"] != "OPEN":
        return None
    
    # Calculate P&L
    entry_price = float(trade["entry_price"])
    position_size = float(trade.get("position_size") or 1)
    direction = str(trade.get("direction", "")).upper()
    
    if direction == "LONG":
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    else:  # SHORT
        pnl_pct = ((entry_price - exit_price) / entry_price) * 100

    pnl_usd = (pnl_pct / 100) * position_size
    if pnl_usd_override is not None:
        pnl_usd = float(pnl_usd_override)
    if pnl_pct_override is not None:
        pnl_pct = float(pnl_pct_override)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    trade_columns = _table_columns(conn, "trades")
    updates = {
        "exit_price": exit_price,
        "pnl_usd": pnl_usd,
        "pnl_pct": pnl_pct,
        "outcome": outcome,
        "ts_close": ts_close,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    set_pairs = [f"{col} = ?" for col in updates.keys() if col in trade_columns]
    params = [updates[col] for col in updates.keys() if col in trade_columns]
    params.append(trade_id)
    cursor.execute(
        f"UPDATE trades SET {', '.join(set_pairs)} WHERE id = ?",
        params,
    )
    
    # Log event
    import json
    event_columns = _table_columns(conn, "trade_events")
    event_row = {
        "trade_id": trade_id,
        "event_type": event_type,
        "event_ts": ts_close,
        "ts": ts_close,
        "price": exit_price,
        "provider": provider,
        "payload": json.dumps(payload),
        "payload_json": json.dumps(payload),
    }
    insert_cols = [col for col in event_row.keys() if col in event_columns]
    placeholders = ", ".join(["?"] * len(insert_cols))
    cursor.execute(
        f"INSERT INTO trade_events ({', '.join(insert_cols)}) VALUES ({placeholders})",
        [event_row[col] for col in insert_cols],
    )
    
    conn.commit()
    conn.close()
    
    return get_trade(trade_id)


def update_trade_sl_tp(trade_id: int, sl_price: Optional[float], tp_price: Optional[float]) -> None:
    """Update trade SL/TP levels"""
    conn = get_connection()
    cursor = conn.cursor()
    trade_columns = _table_columns(conn, "trades")
    updates = {}
    if "sl_price" in trade_columns:
        updates["sl_price"] = sl_price
    if "tp_price" in trade_columns:
        updates["tp_price"] = tp_price
    if "sl" in trade_columns:
        updates["sl"] = sl_price
    if "tp" in trade_columns:
        updates["tp"] = tp_price
    if "updated_at" in trade_columns:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_pairs = [f"{col} = ?" for col in updates.keys()]
    params = list(updates.values()) + [trade_id]
    cursor.execute(f"UPDATE trades SET {', '.join(set_pairs)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_trade_events(trade_id: int) -> List[Dict[str, Any]]:
    """Get all events for a trade"""
    conn = get_connection()
    cursor = conn.cursor()
    columns = _table_columns(conn, "trade_events")
    order_col = "event_ts" if "event_ts" in columns else "ts"
    cursor.execute(f"SELECT * FROM trade_events WHERE trade_id = ? ORDER BY {order_col} DESC", (trade_id,))
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events


def set_trade_chart_paths(trade_id: int, chart_paths: List[str]) -> None:
    """Persist generated chart paths on trade row when schema supports it."""
    conn = get_connection()
    cursor = conn.cursor()
    trade_columns = _table_columns(conn, "trades")
    if "chart_path" in trade_columns:
        value = ",".join(chart_paths[:3])
        cursor.execute("UPDATE trades SET chart_path = ? WHERE id = ?", (value, trade_id))
        conn.commit()
    conn.close()


# Statistics operations
def get_stats(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    """Calculate trading statistics"""
    account = get_account(account_id) if account_id else get_accounts()[0] if get_accounts() else None
    initial_balance = float(account["initial_balance"]) if account else 0.0

    trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    closed_trades = [t for t in trades if t["outcome"] != "OPEN"]
    
    if not closed_trades:
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
            "balance": initial_balance,
            "growth_pct": 0,
            "wins": 0,
            "losses": 0,
            "expectancy": 0,
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
    
    # Calculate max drawdown on equity (starting from initial balance)
    equity = initial_balance
    peak = initial_balance
    max_dd = 0
    for t in sorted(closed_trades, key=lambda x: x.get("ts_close", "")):
        equity += float(t.get("pnl_usd", 0) or 0)
        peak = max(peak, equity)
        dd = ((peak - equity) / peak * 100) if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    # Simple sample Sharpe approximation from trade returns
    returns = [float(t.get("pnl_pct") or 0.0) / 100.0 for t in closed_trades]
    sharpe_ratio = 0.0
    if len(returns) > 1:
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)
        if std_dev > 0:
            sharpe_ratio = (mean_ret / std_dev) * math.sqrt(len(returns))
    
    return {
        "total_trades": len(closed_trades),
        "win_rate": win_rate,
        "total_pnl_usd": total_pnl,
        "avg_win_usd": avg_win,
        "avg_loss_usd": avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": sharpe_ratio,
        "avg_rr": avg_win / avg_loss if avg_loss > 0 else 0,
        "initial_balance": initial_balance,
        "balance": initial_balance + total_pnl,
        "growth_pct": (total_pnl / initial_balance * 100) if initial_balance > 0 else 0,
        "wins": len(wins),
        "losses": len(losses),
        "expectancy": (total_pnl / len(closed_trades)) if closed_trades else 0,
    }


def get_analytics_breakdown(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    """Get directional analytics breakdown"""
    trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    closed_trades = [t for t in trades if t["outcome"] != "OPEN"]
    
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _duration_hours(trade: Dict[str, Any]) -> float:
        opened = _parse_ts(trade.get("ts_open"))
        closed = _parse_ts(trade.get("ts_close"))
        if not opened or not closed:
            return 0.0
        duration = (closed - opened).total_seconds() / 3600.0
        return max(0.0, duration)

    def _trade_rr(trade: Dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[float]]:
        entry = _safe_float(trade.get("entry_price", trade.get("entry")), 0.0)
        sl = _safe_float(trade.get("sl_price", trade.get("sl")), 0.0)
        exit_price = _safe_float(trade.get("exit_price"), 0.0)
        direction = str(trade.get("direction", "")).upper()
        size = _safe_float(trade.get("position_size"), 0.0)

        if entry <= 0 or sl <= 0 or exit_price <= 0:
            return None, None, None

        if direction == "LONG":
            risk_pct = ((entry - sl) / entry) * 100.0
            reward_pct = ((exit_price - entry) / entry) * 100.0
        else:
            risk_pct = ((sl - entry) / entry) * 100.0
            reward_pct = ((entry - exit_price) / entry) * 100.0

        if risk_pct <= 0:
            return None, None, None

        rr = abs(reward_pct / risk_pct)
        risk_usd = size * abs(risk_pct) / 100.0
        reward_usd = size * abs(reward_pct) / 100.0
        return rr, risk_usd, reward_usd

    def _streak_lengths(trades_seq: List[Dict[str, Any]], is_win: bool) -> List[int]:
        streaks: List[int] = []
        current = 0
        for trade in trades_seq:
            pnl = _safe_float(trade.get("pnl_usd"), 0.0)
            match = pnl > 0 if is_win else pnl < 0
            if match:
                current += 1
                continue
            if current > 0:
                streaks.append(current)
                current = 0
        if current > 0:
            streaks.append(current)
        return streaks

    def _avg(values: List[float]) -> float:
        return (sum(values) / len(values)) if values else 0.0

    long_trades = [t for t in closed_trades if str(t.get("direction", "")).upper() == "LONG"]
    short_trades = [t for t in closed_trades if str(t.get("direction", "")).upper() == "SHORT"]
    
    def calc_direction_stats(direction_trades):
        if not direction_trades:
            return {"count": 0, "win_rate": 0, "total_pnl": 0, "avg_pnl": 0, "avg_rr": 0, "max_rr": 0}
        
        wins = [t for t in direction_trades if _safe_float(t.get("pnl_usd"), 0.0) > 0]
        total_pnl = sum(_safe_float(t.get("pnl_usd"), 0.0) for t in direction_trades)
        direction_rr = []
        for trade in direction_trades:
            rr, _, _ = _trade_rr(trade)
            if rr is not None:
                direction_rr.append(rr)
        
        return {
            "count": len(direction_trades),
            "win_rate": (len(wins) / len(direction_trades)) * 100,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / len(direction_trades),
            "avg_rr": _avg(direction_rr),
            "max_rr": max(direction_rr) if direction_rr else 0.0,
        }
    
    by_weekday = {day: {"pnl_usd": 0.0, "count": 0} for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
    by_hour = {f"{hour:02d}:00": {"pnl_usd": 0.0, "count": 0} for hour in range(24)}
    rr_values: List[float] = []
    risk_values: List[float] = []
    reward_values: List[float] = []
    durations_win: List[float] = []
    durations_loss: List[float] = []

    for trade in closed_trades:
        dt = _parse_ts(trade.get("ts_open"))
        if not dt:
            continue
        day = dt.strftime("%a")
        hour = f"{dt.hour:02d}:00"
        pnl = _safe_float(trade.get("pnl_usd"), 0.0)
        if day in by_weekday:
            by_weekday[day]["pnl_usd"] += pnl
            by_weekday[day]["count"] += 1
        if hour in by_hour:
            by_hour[hour]["pnl_usd"] += pnl
            by_hour[hour]["count"] += 1
        rr, risk_usd, reward_usd = _trade_rr(trade)
        if rr is not None:
            rr_values.append(rr)
        if risk_usd is not None:
            risk_values.append(risk_usd)
        if reward_usd is not None and pnl > 0:
            reward_values.append(reward_usd)
        duration = _duration_hours(trade)
        if pnl > 0:
            durations_win.append(duration)
        elif pnl < 0:
            durations_loss.append(duration)

    long_stats = calc_direction_stats(long_trades)
    short_stats = calc_direction_stats(short_trades)
    wins = [t for t in closed_trades if _safe_float(t.get("pnl_usd"), 0.0) > 0]
    losses = [t for t in closed_trades if _safe_float(t.get("pnl_usd"), 0.0) < 0]

    closed_by_time = sorted(closed_trades, key=lambda t: t.get("ts_close") or t.get("ts_open") or "")
    win_streaks = _streak_lengths(closed_by_time, is_win=True)
    loss_streaks = _streak_lengths(closed_by_time, is_win=False)

    win_pnls = [_safe_float(t.get("pnl_usd"), 0.0) for t in wins]
    loss_pnls = [_safe_float(t.get("pnl_usd"), 0.0) for t in losses]

    weekday_values = [by_weekday[d]["pnl_usd"] for d in by_weekday if by_weekday[d]["count"] > 0]
    if len(weekday_values) > 1:
        weekday_mean = _avg(weekday_values)
        weekday_std = math.sqrt(sum((v - weekday_mean) ** 2 for v in weekday_values) / (len(weekday_values) - 1))
    else:
        weekday_std = 0.0

    consistency = max(0.0, min(10.0, 10.0 - (weekday_std / 200.0)))
    reliability = min(10.0, (len(closed_trades) / 5.0))
    discipline = min(10.0, 4.0 + (len(wins) / max(len(closed_trades), 1) * 6.0))
    profitability = min(10.0, max(0.0, (sum(_safe_float(t.get("pnl_usd"), 0.0) for t in closed_trades) / 200.0) + 5.0))
    safety = max(0.0, 10.0 - ((max(loss_streaks) if loss_streaks else 0) * 1.2))
    strategy_dna = {
        "Consistency": round(consistency, 2),
        "Reliability": round(reliability, 2),
        "Discipline": round(discipline, 2),
        "Profitability": round(profitability, 2),
        "Safety": round(safety, 2),
    }
    dna_score = round(sum(strategy_dna.values()) / len(strategy_dna), 2)
    if dna_score >= 8:
        tier = "PROFESSIONAL"
    elif dna_score >= 6:
        tier = "ADVANCED"
    elif dna_score >= 4:
        tier = "DEVELOPING"
    else:
        tier = "BEGINNER"

    win_rate_ratio = len(wins) / len(closed_trades) if closed_trades else 0.0
    loss_rate_ratio = len(losses) / len(closed_trades) if closed_trades else 0.0
    avg_rr_ratio = _avg(rr_values)
    win_loss_ratio = (len(wins) / len(losses)) if losses else 0.0
    rr_relative = (win_loss_ratio / avg_rr_ratio) if avg_rr_ratio > 0 else 0.0
    expected_rr = (win_rate_ratio * avg_rr_ratio) - (loss_rate_ratio * 1.0)

    weekday_active = {k: v for k, v in by_weekday.items() if v["count"] > 0}
    hour_active = {k: v for k, v in by_hour.items() if v["count"] > 0}
    best_day = max(weekday_active.items(), key=lambda item: item[1]["pnl_usd"]) if weekday_active else None
    worst_day = min(weekday_active.items(), key=lambda item: item[1]["pnl_usd"]) if weekday_active else None
    best_hour = max(hour_active.items(), key=lambda item: item[1]["pnl_usd"]) if hour_active else None
    worst_hour = min(hour_active.items(), key=lambda item: item[1]["pnl_usd"]) if hour_active else None

    return {
        "long": long_stats,
        "short": short_stats,
        "by_direction": {"long": long_stats, "short": short_stats},
        "by_weekday": by_weekday,
        "by_hour": by_hour,
        "time_highlights": {
            "best_day": {"label": best_day[0], **best_day[1]} if best_day else None,
            "worst_day": {"label": worst_day[0], **worst_day[1]} if worst_day else None,
            "best_hour": {"label": best_hour[0], **best_hour[1]} if best_hour else None,
            "worst_hour": {"label": worst_hour[0], **worst_hour[1]} if worst_hour else None,
        },
        "wins_losses": {
            "winning": {
                "count": len(wins),
                "best_win": max(win_pnls) if win_pnls else 0.0,
                "avg_win": _avg(win_pnls),
                "avg_duration_hours": _avg(durations_win),
                "max_consecutive": max(win_streaks) if win_streaks else 0,
                "avg_consecutive": _avg([float(s) for s in win_streaks]),
            },
            "losing": {
                "count": len(losses),
                "worst_loss": min(loss_pnls) if loss_pnls else 0.0,
                "avg_loss": _avg(loss_pnls),
                "avg_duration_hours": _avg(durations_loss),
                "max_consecutive": max(loss_streaks) if loss_streaks else 0,
                "avg_consecutive": _avg([float(s) for s in loss_streaks]),
            },
        },
        "risk_reward": {
            "avg_rr_ratio": avg_rr_ratio,
            "max_rr_ratio": max(rr_values) if rr_values else 0.0,
            "win_loss_ratio_relative_rr": rr_relative,
            "expected_rr": expected_rr,
            "avg_risk_trade": _avg(risk_values),
            "avg_reward_trade": _avg(reward_values),
            "by_direction": {
                "long": {"avg_rr": long_stats["avg_rr"], "max_rr": long_stats["max_rr"]},
                "short": {"avg_rr": short_stats["avg_rr"], "max_rr": short_stats["max_rr"]},
            },
        },
        "strategy_dna": strategy_dna,
        "dna_score": dna_score,
        "tier": tier,
        "insights": (
            "Strong positive expectancy profile."
            if expected_rr > 0
            else "Expectancy is negative. Focus on invalidation quality and risk consistency."
        ),
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
    trade_columns = _table_columns(conn, "trades")
    ext_col = "external_id" if "external_id" in trade_columns else "external_trade_id"
    provider_col = "provider" if "provider" in trade_columns else "source"
    cursor.execute(
        f"SELECT * FROM trades WHERE {ext_col} = ? AND {provider_col} = ?",
        (external_id, provider)
    )
    row = cursor.fetchone()
    conn.close()
    return _normalize_trade_row(dict(row)) if row else None


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
    return _normalize_trade_row(dict(row)) if row else None
