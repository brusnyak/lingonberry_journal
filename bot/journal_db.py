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
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def capture_indicators_at_timestamp(
    symbol: str,
    asset_type: str,
    timeframe: str,
    timestamp: str,
) -> Dict[str, Optional[float]]:
    """
    Capture indicator values at a specific timestamp
    
    Returns dict with: ema_9, ema_21, ema_50, ema_200, vwap
    """
    import pandas as pd
    from datetime import timedelta
    from infra.market_data import load_ohlcv_with_cache
    
    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        # Load data with some context
        start = ts - timedelta(days=30)
        end = ts + timedelta(hours=1)
        
        df = load_ohlcv_with_cache(
            symbol=symbol,
            asset_type=asset_type,
            timeframe=timeframe,
            start=start,
            end=end,
            ttl_seconds=0,  # Force fresh data to ensure indicators are calculated
        )
        
        if df.empty:
            print(f"⚠️ No market data found for {symbol} at {timestamp}")
            return {}
        
        # Find the candle closest to the timestamp
        df['ts'] = pd.to_datetime(df['ts'], utc=True)
        time_diffs = abs(df['ts'] - ts)
        closest_idx = time_diffs.idxmin()
        row = df.loc[closest_idx]
        
        # Extract indicator values
        indicators = {}
        for col in ['ema_9', 'ema_21', 'ema_50', 'ema_200', 'vwap']:
            if col in row and pd.notnull(row[col]):
                indicators[col] = float(row[col])
            else:
                indicators[col] = None
        
        return indicators
        
    except Exception as e:
        print(f"Error capturing indicators: {e}")
        import traceback
        traceback.print_exc()
        return {}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _normalize_trade_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Return a trade row with both legacy and v2 field aliases."""
    import json
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

    trade["entry"] = trade.get("entry", entry_price)
    trade["sl"] = trade.get("sl", sl_price)
    trade["tp"] = trade.get("tp", tp_price)

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
    
    # Deserialize indicator_data if present
    if "indicator_data" in trade and trade["indicator_data"]:
        try:
            if isinstance(trade["indicator_data"], str):
                trade["indicator_data"] = json.loads(trade["indicator_data"])
        except:
            trade["indicator_data"] = {}
    
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
            rule_template TEXT,
            consistency_pct REAL,
            min_trading_days INTEGER,
            min_profitable_days INTEGER,
            profitable_day_threshold_pct REAL,
            static_drawdown_floor REAL,
            inactivity_limit_days INTEGER,
            payout_frequency_days INTEGER,
            timezone_name TEXT DEFAULT 'UTC',
            timezone TEXT DEFAULT 'UTC', -- Legacy support
            current_balance REAL DEFAULT 10000, -- Legacy support
            status TEXT DEFAULT 'ACTIVE', -- Legacy support
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

    # Migration for missing columns
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
    rule_template: Optional[str] = None,
    consistency_pct: Optional[float] = None,
    min_trading_days: Optional[int] = None,
    min_profitable_days: Optional[int] = None,
    profitable_day_threshold_pct: Optional[float] = None,
    static_drawdown_floor: Optional[float] = None,
    inactivity_limit_days: Optional[int] = None,
    payout_frequency_days: Optional[int] = None,
    timezone_name: str = "UTC",
) -> int:
    """Create a new trading account"""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        INSERT INTO accounts (
            name, currency, initial_balance, max_daily_loss_pct,
            max_total_loss_pct, profit_target_pct, risk_per_trade_pct,
            firm_name, broker, platform, rule_template, consistency_pct,
            min_trading_days, min_profitable_days, profitable_day_threshold_pct,
            static_drawdown_floor, inactivity_limit_days, payout_frequency_days,
            timezone_name, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name, currency, initial_balance, max_daily_loss_pct,
            max_total_loss_pct, profit_target_pct, risk_per_trade_pct,
            firm_name, broker, platform, rule_template, consistency_pct,
            min_trading_days, min_profitable_days, profitable_day_threshold_pct,
            static_drawdown_floor, inactivity_limit_days, payout_frequency_days,
            timezone_name,
            now, now
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
    account = dict(row) if row else None
    if account and account.get("static_drawdown_floor") is None and account.get("initial_balance") is not None and account.get("max_total_loss_pct") is not None:
        account["static_drawdown_floor"] = float(account["initial_balance"]) * (1 - float(account["max_total_loss_pct"]) / 100.0)
    return account


def update_account_rules(
    account_id: int,
    max_daily_loss_pct: float,
    max_total_loss_pct: float,
    profit_target_pct: float,
    risk_per_trade_pct: float,
    consistency_pct: Optional[float] = None,
    min_trading_days: Optional[int] = None,
    min_profitable_days: Optional[int] = None,
    profitable_day_threshold_pct: Optional[float] = None,
    static_drawdown_floor: Optional[float] = None,
    inactivity_limit_days: Optional[int] = None,
    payout_frequency_days: Optional[int] = None,
) -> None:
    """Update account risk rules"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE accounts
        SET max_daily_loss_pct = ?, max_total_loss_pct = ?,
            profit_target_pct = ?, risk_per_trade_pct = ?,
            consistency_pct = ?, min_trading_days = ?,
            min_profitable_days = ?, profitable_day_threshold_pct = ?,
            static_drawdown_floor = ?, inactivity_limit_days = ?,
            payout_frequency_days = ?
        WHERE id = ?
        """,
        (
            max_daily_loss_pct,
            max_total_loss_pct,
            profit_target_pct,
            risk_per_trade_pct,
            consistency_pct,
            min_trading_days,
            min_profitable_days,
            profitable_day_threshold_pct,
            static_drawdown_floor,
            inactivity_limit_days,
            payout_frequency_days,
            account_id,
        ),
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
    indicator_data: Optional[Dict[str, Any]] = None,
) -> int:
    """Create a new trade"""
    import json
    from bot.session_detector import detect_session
    conn = get_connection()
    cursor = conn.cursor()
    trade_columns = _table_columns(conn, "trades")
    if external_id:
        ext_col = "external_id" if "external_id" in trade_columns else ("external_trade_id" if "external_trade_id" in trade_columns else None)
        if ext_col:
            cursor.execute(
                f"SELECT id FROM trades WHERE account_id = ? AND {ext_col} = ?",
                (account_id, external_id)
            )
            existing = cursor.fetchone()
            if existing:
                conn.close()
                return None

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
        "rr_ratio": compute_rr_ratio(entry_price, sl_price, tp_price),
        "session": _normalize_session_name(session or detect_session(ts_open)),
        "timeframe": timeframe,
        "strategy": strategy,
        "notes": notes,
        "external_id": external_id,
        "external_trade_id": external_id,
        "provider": provider,
        "source": provider or "manual_bot",
        "indicator_data": json.dumps(indicator_data) if indicator_data else None,
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


def add_manual_trade(
    account_id: int,
    symbol: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    ts_open: str,
    ts_close: str,
    lots: float = 0.1,
    asset_type: str = "forex",
    timeframe: str = "M30",
    notes: str = "",
    outcome: str = "TP",
    sl_price: float = None,
    tp_price: float = None,
    indicator_data: dict = None,
) -> int:
    """Add a finished trade manually"""
    import json
    from bot.session_detector import detect_session
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calculate P&L
    pnl_usd = 0.0
    pnl_pct = 0.0
    if direction.upper() == "LONG":
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    else:
        pnl_pct = ((entry_price - exit_price) / entry_price) * 100
    
    # Simple estimate: 1 lot = 100,000 units, so 1 pip = $10 approx
    # This is vary crude but for manual logs it might be enough if not provided
    pnl_usd = (pnl_pct / 100) * 100000 * lots 

    indicator_json = json.dumps(indicator_data) if indicator_data else None

    # Use provided SL/TP or extract from indicator_data if present
    if sl_price is None and indicator_data:
        sl_price = indicator_data.get("sl")
    if tp_price is None and indicator_data:
        tp_price = indicator_data.get("tp")
    
    # Provide defaults for NOT NULL constraints
    # If still None, calculate reasonable defaults based on entry and direction
    if sl_price is None:
        # Default SL: 2% away from entry
        if direction.upper() == "LONG":
            sl_price = entry_price * 0.98
        else:
            sl_price = entry_price * 1.02
    
    if tp_price is None:
        # Default TP: use exit_price or 2% profit
        tp_price = exit_price if exit_price else (entry_price * 1.02 if direction.upper() == "LONG" else entry_price * 0.98)

    # Calculate RR ratio
    rr_ratio = None
    if sl_price and tp_price and entry_price:
        risk = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)
        if risk > 0:
            rr_ratio = reward / risk
    
    # Detect trading session based on UTC timestamp
    session = _normalize_session_name(detect_session(ts_open))

    cursor.execute(
        """
        INSERT INTO trades (
            account_id, symbol, asset_type, direction,
            entry, sl, tp, exit_price, ts_open, ts_close,
            lot_size, pnl_usd, pnl_pct, rr_ratio, session, timeframe,
            outcome, notes, source, indicator_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            account_id, symbol, asset_type, direction.upper(),
            entry_price, sl_price, tp_price, exit_price,
            ts_open, ts_close,
            lots, pnl_usd, pnl_pct, rr_ratio, session, timeframe,
            outcome, notes, "manual_web", indicator_json
        ),
    )
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trade_id


def update_trade_chart_path(trade_id: int, chart_path: str) -> None:
    """Update the chart_path column for a trade"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE trades SET chart_path = ? WHERE id = ?", (chart_path, trade_id))
    conn.commit()
    conn.close()


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
def get_trades_by_week(
    week_start: str,
    account_id: Optional[int] = None,
    is_perfect: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Get trades for a specific week

    Args:
        week_start: ISO date string for Monday of the week (e.g., '2026-03-02')
        account_id: Optional account filter
        is_perfect: Optional filter for perfect trades (True/False/None for all)

    Returns:
        List of trade dictionaries
    """
    from datetime import datetime, timedelta

    conn = get_connection()
    cursor = conn.cursor()

    # Calculate week end (Sunday)
    week_start_dt = datetime.fromisoformat(week_start)
    week_end_dt = week_start_dt + timedelta(days=7)
    week_end = week_end_dt.strftime('%Y-%m-%d')

    query = "SELECT * FROM trades WHERE ts_open >= ? AND ts_open < ?"
    params = [week_start, week_end]

    if account_id is not None:
        query += " AND account_id = ?"
        params.append(account_id)

    if is_perfect is not None:
        query += " AND is_perfect = ?"
        params.append(1 if is_perfect else 0)

    query += " ORDER BY ts_open ASC"

    cursor.execute(query, params)
    trades = [_normalize_trade_row(dict(row)) for row in cursor.fetchall()]
    conn.close()
    return trades
def get_week_stats(
    week_start: str,
    account_id: Optional[int] = None,
    is_perfect: Optional[bool] = None,
) -> Dict[str, Any]:
    """Get statistics for a specific week

    Args:
        week_start: ISO date string for Monday of the week
        account_id: Optional account filter
        is_perfect: Optional filter for perfect trades

    Returns:
        Dictionary with week statistics
    """
    trades = get_trades_by_week(week_start, account_id, is_perfect)

    if not trades:
        return {
            "week_start": week_start,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "net_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "avg_rr": 0,
        }

    closed_trades = [t for t in trades if t.get("outcome") in ("TP", "SL", "MANUAL")]
    wins = [t for t in closed_trades if t.get("pnl_usd", 0) > 0]
    losses = [t for t in closed_trades if t.get("pnl_usd", 0) < 0]

    total_wins = sum(t.get("pnl_usd", 0) for t in wins)
    total_losses = abs(sum(t.get("pnl_usd", 0) for t in losses))

    profit_factor = 0
    if total_losses > 0:
        profit_factor = total_wins / total_losses
    elif total_wins > 0:
        profit_factor = float('inf')

    # Calculate average R:R
    rr_values = []
    for t in closed_trades:
        entry = t.get("entry_price")
        sl = t.get("sl_price")
        tp = t.get("tp_price")
        if entry and sl and tp:
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            if risk > 0:
                rr_values.append(reward / risk)

    return {
        "week_start": week_start,
        "total_trades": len(trades),
        "closed_trades": len(closed_trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed_trades) * 100, 1) if closed_trades else 0,
        "net_pnl": round(sum(t.get("pnl_usd", 0) for t in closed_trades), 2),
        "avg_win": round(total_wins / len(wins), 2) if wins else 0,
        "avg_loss": round(total_losses / len(losses), 2) if losses else 0,
        "profit_factor": None if profit_factor == float('inf') else round(profit_factor, 2),
        "best_trade": round(max((t.get("pnl_usd", 0) for t in closed_trades), default=0), 2),
        "worst_trade": round(min((t.get("pnl_usd", 0) for t in closed_trades), default=0), 2),
        "avg_rr": round(sum(rr_values) / len(rr_values), 2) if rr_values else 0,
    }




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
    exit_indicators: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Close a trade and calculate P&L"""
    import json
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
    
    # Merge exit indicators with existing indicator_data
    indicator_data = {}
    if trade.get("indicator_data"):
        # Already deserialized by _normalize_trade_row
        if isinstance(trade["indicator_data"], dict):
            indicator_data = trade["indicator_data"].copy()
        else:
            try:
                indicator_data = json.loads(trade["indicator_data"])
            except:
                pass
    
    if exit_indicators:
        indicator_data["exit"] = exit_indicators
    
    conn = get_connection()
    cursor = conn.cursor()
    
    trade_columns = _table_columns(conn, "trades")
    updates = {
        "exit_price": exit_price,
        "pnl_usd": pnl_usd,
        "pnl_pct": pnl_pct,
        "outcome": outcome,
        "ts_close": ts_close,
        "indicator_data": json.dumps(indicator_data) if indicator_data else None,
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
    trade = get_trade(trade_id)
    updates = {}
    if "sl_price" in trade_columns:
        updates["sl_price"] = sl_price
    if "tp_price" in trade_columns:
        updates["tp_price"] = tp_price
    if "sl" in trade_columns:
        updates["sl"] = sl_price
    if "tp" in trade_columns:
        updates["tp"] = tp_price
    if "rr_ratio" in trade_columns and trade:
        updates["rr_ratio"] = compute_rr_ratio(
            trade.get("entry_price", trade.get("entry")),
            sl_price,
            tp_price,
        )
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


def get_daily_loss_state(
    account: Optional[Dict[str, Any]],
    trades: List[Dict[str, Any]],
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build daily-loss history from start-of-day balance and intraday realized PnL."""
    if not account or account.get("max_daily_loss_pct") is None:
        return {
            "limit_usd": None,
            "history": [],
            "current": None,
            "has_historical_breach": False,
        }

    initial_balance = float(account.get("initial_balance") or 0.0)
    daily_loss_limit = initial_balance * float(account.get("max_daily_loss_pct") or 0.0) / 100.0
    closed_trades = [t for t in trades if t.get("outcome") != "OPEN"]
    closed_trades.sort(key=lambda t: _parse_timestamp(t.get("ts_close") or t.get("ts_open")) or datetime.min.replace(tzinfo=timezone.utc))

    history_map: Dict[str, Dict[str, Any]] = {}
    running_balance = initial_balance

    for trade in closed_trades:
        trade_ts = _parse_timestamp(trade.get("ts_close") or trade.get("ts_open"))
        if not trade_ts:
            continue
        day_key = trade_ts.date().isoformat()
        if day_key not in history_map:
            history_map[day_key] = {
                "date": day_key,
                "start_balance": running_balance,
                "end_balance": running_balance,
                "realized_pnl": 0.0,
                "intraday_low_pnl": 0.0,
                "trade_count": 0,
                "open_pnl_impact": 0.0,
            }

        bucket = history_map[day_key]
        pnl = float(trade.get("pnl_usd") or 0.0)
        bucket["trade_count"] += 1
        bucket["realized_pnl"] += pnl
        bucket["intraday_low_pnl"] = min(bucket["intraday_low_pnl"], bucket["realized_pnl"])
        running_balance += pnl
        bucket["end_balance"] = running_balance

    today = (as_of or datetime.now(timezone.utc)).date().isoformat()
    if today not in history_map:
        history_map[today] = {
            "date": today,
            "start_balance": running_balance,
            "end_balance": running_balance,
            "realized_pnl": 0.0,
            "intraday_low_pnl": 0.0,
            "trade_count": 0,
            "open_pnl_impact": 0.0,
        }

    history = []
    has_historical_breach = False
    for day_key in sorted(history_map.keys()):
        bucket = history_map[day_key]
        current_drawdown_usd = max(0.0, -(bucket["realized_pnl"] + bucket["open_pnl_impact"]))
        worst_drawdown_usd = max(0.0, -bucket["intraday_low_pnl"])
        breached = daily_loss_limit > 0 and worst_drawdown_usd >= (daily_loss_limit - 1e-9)
        has_historical_breach = has_historical_breach or breached
        bucket["daily_loss_limit"] = daily_loss_limit
        bucket["daily_loss_floor"] = bucket["start_balance"] - daily_loss_limit
        bucket["current_drawdown_usd"] = current_drawdown_usd
        bucket["worst_drawdown_usd"] = worst_drawdown_usd
        bucket["remaining_usd"] = daily_loss_limit - current_drawdown_usd
        bucket["breached"] = breached
        history.append(bucket)

    current = next((bucket for bucket in history if bucket["date"] == today), history[-1] if history else None)
    return {
        "limit_usd": daily_loss_limit,
        "history": history,
        "current": current,
        "has_historical_breach": has_historical_breach,
    }


def backfill_trade_metadata(account_id: Optional[int] = None) -> Dict[str, int]:
    """One-time normalization for persisted session labels and RR ratios."""
    from bot.session_detector import detect_session

    conn = get_connection()
    cursor = conn.cursor()
    trade_columns = _table_columns(conn, "trades")

    query = "SELECT * FROM trades WHERE 1=1"
    params: List[Any] = []
    if account_id is not None and "account_id" in trade_columns:
        query += " AND account_id = ?"
        params.append(account_id)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    session_updates = 0
    rr_updates = 0
    touched = 0

    for row in rows:
        trade = dict(row)
        updates: Dict[str, Any] = {}

        if "session" in trade_columns:
            derived_session = _normalize_session_name(trade.get("session") or detect_session(trade.get("ts_open", "")))
            if trade.get("session") != derived_session:
                updates["session"] = derived_session
                session_updates += 1

        if "rr_ratio" in trade_columns:
            rr_ratio = compute_rr_ratio(
                trade.get("entry_price", trade.get("entry")),
                trade.get("sl_price", trade.get("sl")),
                trade.get("tp_price", trade.get("tp")),
            )
            existing_rr = _safe_float(trade.get("rr_ratio"))
            if rr_ratio is not None and (existing_rr is None or abs(existing_rr - rr_ratio) > 1e-9):
                updates["rr_ratio"] = rr_ratio
                rr_updates += 1

        if updates:
            if "updated_at" in trade_columns:
                updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            set_clause = ", ".join(f"{column} = ?" for column in updates.keys())
            cursor.execute(
                f"UPDATE trades SET {set_clause} WHERE id = ?",
                list(updates.values()) + [trade["id"]],
            )
            touched += 1

    conn.commit()
    conn.close()
    return {
        "checked": len(rows),
        "updated": touched,
        "session_updates": session_updates,
        "rr_updates": rr_updates,
    }


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
            "daily_pnl": 0,
        }
    
    wins = [t for t in closed_trades if (t.get("pnl_usd") or 0) > 0]
    losses = [t for t in closed_trades if (t.get("pnl_usd") or 0) < 0]
    today_utc = datetime.now(timezone.utc).date()
    daily_pnl = 0.0
    for t in closed_trades:
        ts_value = t.get("ts_close") or t.get("ts_open")
        if not ts_value:
            continue
        try:
            trade_date = datetime.fromisoformat(str(ts_value).replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if trade_date == today_utc:
            daily_pnl += float(t.get("pnl_usd", 0) or 0)
    
    total_pnl = sum(t.get("pnl_usd", 0) for t in closed_trades)
    # Fix: Filter out None values for accurate profit factor calculation
    total_wins = sum(t["pnl_usd"] for t in wins if t.get("pnl_usd") is not None)
    total_losses = abs(sum(t["pnl_usd"] for t in losses if t.get("pnl_usd") is not None))
    
    win_rate = (len(wins) / len(closed_trades)) * 100 if closed_trades else 0
    avg_win = total_wins / len(wins) if wins else 0
    avg_loss = total_losses / len(losses) if losses else 0
    # Fix: Handle edge case where all trades are wins (no losses)
    profit_factor = total_wins / total_losses if total_losses > 0 else (float('inf') if total_wins > 0 else 0)
    
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
    
    # Convert infinity to None for JSON serialization
    if math.isinf(profit_factor):
        profit_factor = None
    
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
        "daily_pnl": daily_pnl,
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

    def _safe_str(value: Any, default: str = "") -> str:
        if value is None:
            return default
        return str(value)

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


def analyze_direction_correctness(
    trade_id: Optional[int] = None,
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze if trade direction was correct by checking if price reached TP after SL hit.
    Can analyze a single trade or batch analyze trades.
    
    Returns:
        For single trade: {"trade_id": int, "direction_correct": bool, "analysis": str}
        For batch: {"analyzed": int, "updated": int, "results": [...]}
    """
    import pandas as pd
    from infra.market_data import load_ohlcv_with_cache
    
    if trade_id:
        trades = [get_trade(trade_id)]
        if not trades[0]:
            return {"error": f"Trade {trade_id} not found"}
    else:
        trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
        # Analyze all closed trades
        trades = [
            t for t in trades 
            if t["outcome"] not in ["OPEN"] 
        ]
    
    results = []
    updated_count = 0
    
    for trade in trades:
        try:
            # Validate required fields
            if not trade.get("ts_close"):
                results.append({
                    "trade_id": trade["id"],
                    "direction_correct": None,
                    "analysis": "No close timestamp"
                })
                continue
            
            # Get timeframe, default to m15 if not set
            timeframe = trade.get("timeframe") or "m15"
            
            # Parse timestamps
            ts_close = datetime.fromisoformat(trade["ts_close"].replace("Z", "+00:00"))
            
            # Load market data from close time to EOD (or +24h)
            end_time = ts_close + timedelta(hours=24)
            
            df = load_ohlcv_with_cache(
                symbol=trade["symbol"],
                asset_type=trade.get("asset_type") or "forex",
                timeframe=timeframe,
                start=ts_close,
                end=end_time,
                ttl_seconds=3600,  # Cache for 1 hour
            )
            
            if df.empty:
                results.append({
                    "trade_id": trade["id"],
                    "direction_correct": None,
                    "analysis": "No market data available"
                })
                continue
            
            direction = str(trade.get("direction", "")).upper()
            
            # 🟢 RULE 1: If it's a win, direction was correct by definition
            if trade.get("pnl_usd", 0) > 0 or trade.get("outcome") == "TP":
                direction_correct = 1
                analysis = "Win: Direction confirmed by profit"
                
                # Update DB
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE trades SET direction_correct = ? WHERE id = ?", (1, trade["id"]))
                conn.commit()
                conn.close()
                
                updated_count += 1
                results.append({"trade_id": trade["id"], "direction_correct": True, "analysis": analysis})
                continue

            # 🔴 RULE 2: For losers, check if it was a "stop-out" (direction was right but SL was too tight)
            if not trade.get("sl_price") or not trade.get("tp_price"):
                results.append({
                    "trade_id": trade["id"],
                    "direction_correct": 0,
                    "analysis": "Loss: No SL/TP defined for stop-out check"
                })
                continue

            if not direction or direction not in ["LONG", "SHORT"]:
                results.append({
                    "trade_id": trade["id"],
                    "direction_correct": 0,
                    "analysis": f"Invalid direction: {trade.get('direction')}"
                })
                continue
            
            # Check if price reached TP after SL was hit
            direction_correct = False
            
            if direction == "LONG":
                # For LONG: check if high reached or exceeded TP
                max_price = df["high"].max()
                direction_correct = max_price >= tp
                analysis = f"Max price after SL: {max_price:.5f}, TP: {tp:.5f}"
            else:  # SHORT
                # For SHORT: check if low reached or went below TP
                min_price = df["low"].min()
                direction_correct = min_price <= tp
                analysis = f"Min price after SL: {min_price:.5f}, TP: {tp:.5f}"
            
            # Update trade in database
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE trades SET direction_correct = ? WHERE id = ?",
                (1 if direction_correct else 0, trade["id"])
            )
            conn.commit()
            conn.close()
            updated_count += 1
            
            results.append({
                "trade_id": trade["id"],
                "direction_correct": direction_correct,
                "analysis": analysis
            })
            
        except Exception as e:
            import traceback
            results.append({
                "trade_id": trade["id"],
                "direction_correct": None,
                "analysis": f"Error: {str(e)}\n{traceback.format_exc()}"
            })
    
    if trade_id:
        return results[0] if results else {"error": "No analysis performed"}
    else:
        return {
            "analyzed": len(results),
            "updated": updated_count,
            "results": results
        }


def get_direction_accuracy_stats(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate direction accuracy statistics.
    
    Returns:
        {
            "overall_accuracy": float,  # % of trades with correct direction
            "win_accuracy": float,      # % of wins with correct direction
            "loss_accuracy": float,     # % of losses with correct direction
            "total_analyzed": int,
            "correct_direction": int,
            "by_direction": {...}
        }
    """
    trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    closed_trades = [t for t in trades if t["outcome"] != "OPEN"]
    
    # Filter trades that have been analyzed
    analyzed_trades = [t for t in closed_trades if t.get("direction_correct") is not None]
    
    if not analyzed_trades:
        # If not analyzed, attempt to auto-analyze (minimal cost for winners)
        analyze_direction_correctness(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
        trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
        closed_trades = [t for t in trades if t["outcome"] != "OPEN"]
        analyzed_trades = [t for t in closed_trades if t.get("direction_correct") is not None]

    if not analyzed_trades:
        return {
            "overall_accuracy": 0,
            "win_accuracy": 0,
            "loss_accuracy": 0,
            "total_analyzed": 0,
            "correct_direction": 0,
            "by_direction": {
                "long": {"total": 0, "correct": 0, "accuracy": 0},
                "short": {"total": 0, "correct": 0, "accuracy": 0}
            },
            "note": "No trades analyzed. Try logging some wins or running analysis."
        }
    
    wins = [t for t in analyzed_trades if t.get("pnl_usd", 0) > 0]
    losses = [t for t in analyzed_trades if t.get("pnl_usd", 0) < 0]
    
    correct_overall = [t for t in analyzed_trades if t["direction_correct"] == 1]
    correct_wins = [t for t in wins if t["direction_correct"] == 1]
    correct_losses = [t for t in losses if t["direction_correct"] == 1]
    
    long_trades = [t for t in analyzed_trades if t["direction"].upper() == "LONG"]
    short_trades = [t for t in analyzed_trades if t["direction"].upper() == "SHORT"]
    
    long_correct = [t for t in long_trades if t["direction_correct"] == 1]
    short_correct = [t for t in short_trades if t["direction_correct"] == 1]
    
    return {
        "overall_accuracy": (len(correct_overall) / len(analyzed_trades) * 100) if analyzed_trades else 0,
        "win_accuracy": (len(correct_wins) / len(wins) * 100) if wins else 0,
        "loss_accuracy": (len(correct_losses) / len(losses) * 100) if losses else 0,
        "total_analyzed": len(analyzed_trades),
        "correct_direction": len(correct_overall),
        "by_direction": {
            "long": {
                "total": len(long_trades),
                "correct": len(long_correct),
                "accuracy": (len(long_correct) / len(long_trades) * 100) if long_trades else 0,
            },
            "short": {
                "total": len(short_trades),
                "correct": len(short_correct),
                "accuracy": (len(short_correct) / len(short_trades) * 100) if short_trades else 0,
            },
        },
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
    from datetime import datetime, timedelta
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calculate week_end (Sunday)
    week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
    week_end_date = week_start_date + timedelta(days=6)
    week_end = week_end_date.strftime('%Y-%m-%d')
    
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
                account_id, week_start, week_end, summary, key_wins,
                key_mistakes, next_week_focus, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (account_id, week_start, week_end, summary, key_wins, key_mistakes, next_week_focus),
        )
    
    conn.commit()
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
        "week_end": week_end,
        "summary": summary,
        "key_wins": key_wins,
        "key_mistakes": key_mistakes,
        "next_week_focus": next_week_focus,
    }


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
def save_drawing(trade_id: int, drawing_type: str, drawing_data: str, account_id: int = 1, symbol: str = "", timeframe: str = "H1") -> int:
    """Save a drawing for a trade"""
    import json
    from datetime import datetime, timezone
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Parse drawing_data if it's a JSON string
    try:
        data = json.loads(drawing_data) if isinstance(drawing_data, str) else drawing_data
    except:
        data = {"raw": drawing_data}
    
    # Extract points and style from the drawing data
    points_json = json.dumps(data.get("points", []))
    style_json = json.dumps(data.get("style", {}))
    note = data.get("note", "")
    
    # Get trade info if not provided
    if not symbol or not account_id:
        cursor.execute("SELECT symbol, account_id FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        if row:
            symbol = symbol or row[0]
            account_id = account_id or row[1]
    
    cursor.execute(
        """INSERT INTO drawings (
            account_id, trade_id, source, symbol, timeframe,
            drawing_type, points_json, style_json, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            account_id, trade_id, "manual_web", symbol, timeframe,
            drawing_type, points_json, style_json, note,
            datetime.now(timezone.utc).isoformat()
        )
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
