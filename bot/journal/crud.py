"""
CRUD operations for accounts, trades, reviews, drawings, monte carlo, webhooks.

All functions share the same signatures as the original journal_db.py.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bot.journal.schema import (
    DB_PATH,
    _normalize_session_name,
    _normalize_trade_row,
    _parse_timestamp,
    _safe_float,
    _table_columns,
    compute_rr_ratio,
    get_connection,
)


# ── Account operations ───────────────────────────────────────────────────────


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
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts ORDER BY created_at DESC")
    accounts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return accounts


def get_account(account_id: int) -> Optional[Dict[str, Any]]:
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
        (max_daily_loss_pct, max_total_loss_pct, profit_target_pct, risk_per_trade_pct,
         consistency_pct, min_trading_days, min_profitable_days, profitable_day_threshold_pct,
         static_drawdown_floor, inactivity_limit_days, payout_frequency_days, account_id),
    )
    conn.commit()
    conn.close()


# ── Trade operations ─────────────────────────────────────────────────────────


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
) -> Optional[int]:
    from bot.journal.schema import get_connection, _table_columns, compute_rr_ratio, _normalize_session_name
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
        "position_size": position_size,
        "lot_size": position_size,
        "sl_price": sl_price if sl_price is not None else entry_price,
        "tp_price": tp_price if tp_price is not None else entry_price,
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
    from bot.session_detector import detect_session

    conn = get_connection()
    cursor = conn.cursor()

    pnl_usd = 0.0
    pnl_pct = 0.0
    if direction.upper() == "LONG":
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    else:
        pnl_pct = ((entry_price - exit_price) / entry_price) * 100
    pnl_usd = (pnl_pct / 100) * 100000 * lots

    indicator_json = json.dumps(indicator_data) if indicator_data else None

    if sl_price is None and indicator_data:
        sl_price = indicator_data.get("sl")
    if tp_price is None and indicator_data:
        tp_price = indicator_data.get("tp")

    if sl_price is None:
        if direction.upper() == "LONG":
            sl_price = entry_price * 0.98
        else:
            sl_price = entry_price * 1.02

    if tp_price is None:
        tp_price = exit_price if exit_price else (entry_price * 1.02 if direction.upper() == "LONG" else entry_price * 0.98)

    rr_ratio = None
    if sl_price and tp_price and entry_price:
        risk = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)
        if risk > 0:
            rr_ratio = reward / risk

    session = _normalize_session_name(detect_session(ts_open))

    cursor.execute(
        """INSERT INTO trades (
            account_id, symbol, asset_type, direction,
            entry, sl, tp, exit_price, ts_open, ts_close,
            lot_size, pnl_usd, pnl_pct, rr_ratio, session, timeframe,
            outcome, notes, source, indicator_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (account_id, symbol, asset_type, direction.upper(),
         entry_price, sl_price, tp_price, exit_price,
         ts_open, ts_close,
         lots, pnl_usd, pnl_pct, rr_ratio, session, timeframe,
         outcome, notes, "manual_web", indicator_json),
    )
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trade_id


def get_trade(trade_id: int) -> Optional[Dict[str, Any]]:
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
    conn = get_connection()
    cursor = conn.cursor()

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


def get_open_trades(account_id: Optional[int] = None) -> List[Dict[str, Any]]:
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


def update_trade_chart_path(trade_id: int, chart_path: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE trades SET chart_path = ? WHERE id = ?", (chart_path, trade_id))
    conn.commit()
    conn.close()


def set_trade_chart_paths(trade_id: int, chart_paths: List[str]) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    trade_columns = _table_columns(conn, "trades")
    if "chart_path" in trade_columns:
        value = ",".join(chart_paths[:3])
        cursor.execute("UPDATE trades SET chart_path = ? WHERE id = ?", (value, trade_id))
        conn.commit()
    conn.close()


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
    if ts_close is None:
        ts_close = datetime.now(timezone.utc).isoformat()

    trade = get_trade(trade_id)
    if not trade or trade["outcome"] != "OPEN":
        return None

    entry_price = float(trade["entry_price"])
    position_size = float(trade.get("position_size") or 1)
    direction = str(trade.get("direction", "")).upper()

    if direction == "LONG":
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    else:
        pnl_pct = ((entry_price - exit_price) / entry_price) * 100

    pnl_usd = (pnl_pct / 100) * position_size
    if pnl_usd_override is not None:
        pnl_usd = float(pnl_usd_override)
    if pnl_pct_override is not None:
        pnl_pct = float(pnl_pct_override)

    indicator_data = {}
    if trade.get("indicator_data"):
        if isinstance(trade["indicator_data"], dict):
            indicator_data = trade["indicator_data"].copy()
        else:
            try:
                indicator_data = json.loads(trade["indicator_data"])
            except Exception:
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
    cursor.execute(f"UPDATE trades SET {', '.join(set_pairs)} WHERE id = ?", params)

    # Log event
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
    if not account or account.get("max_daily_loss_pct") is None:
        return {"limit_usd": None, "history": [], "current": None, "has_historical_breach": False}

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
                "date": day_key, "start_balance": running_balance,
                "end_balance": running_balance, "realized_pnl": 0.0,
                "intraday_low_pnl": 0.0, "trade_count": 0, "open_pnl_impact": 0.0,
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
            "date": today, "start_balance": running_balance,
            "end_balance": running_balance, "realized_pnl": 0.0,
            "intraday_low_pnl": 0.0, "trade_count": 0, "open_pnl_impact": 0.0,
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
    return {"checked": len(rows), "updated": touched, "session_updates": session_updates, "rr_updates": rr_updates}


# ── Review operations ────────────────────────────────────────────────────────


def upsert_trade_review_note(
    trade_id: int,
    reviewer_note: Optional[str] = None,
    should_have_done_entry: Optional[str] = None,
    should_have_done_exit: Optional[str] = None,
    should_have_done_sl: Optional[str] = None,
    should_have_done_tp: Optional[str] = None,
    week_start: Optional[str] = None,
) -> Dict[str, Any]:
    trade = get_trade(trade_id)
    if not trade:
        raise ValueError(f"Trade {trade_id} not found")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM trade_reviews WHERE trade_id = ?", (trade_id,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            """UPDATE trade_reviews
               SET reviewer_note = ?, should_have_done_entry = ?,
                   should_have_done_exit = ?, should_have_done_sl = ?,
                   should_have_done_tp = ?, week_start = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE trade_id = ?""",
            (reviewer_note, should_have_done_entry, should_have_done_exit,
             should_have_done_sl, should_have_done_tp, week_start, trade_id),
        )
    else:
        cursor.execute(
            """INSERT INTO trade_reviews (
                trade_id, reviewer_note, should_have_done_entry,
                should_have_done_exit, should_have_done_sl,
                should_have_done_tp, week_start
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (trade_id, reviewer_note, should_have_done_entry,
             should_have_done_exit, should_have_done_sl,
             should_have_done_tp, week_start),
        )

    conn.commit()
    cursor.execute("SELECT * FROM trade_reviews WHERE trade_id = ?", (trade_id,))
    review = dict(cursor.fetchone())
    conn.close()
    return review


def get_weekly_review(account_id: int, week_start: str) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM weekly_reviews WHERE account_id = ? AND week_start = ?",
        (account_id, week_start),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"account_id": account_id, "week_start": week_start,
            "summary": None, "key_wins": None, "key_mistakes": None, "next_week_focus": None}


def upsert_weekly_review(
    account_id: int,
    week_start: str,
    summary: Optional[str] = None,
    key_wins: Optional[str] = None,
    key_mistakes: Optional[str] = None,
    next_week_focus: Optional[str] = None,
) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
    week_end_date = week_start_date + timedelta(days=6)
    week_end = week_end_date.strftime('%Y-%m-%d')

    cursor.execute(
        "SELECT id FROM weekly_reviews WHERE account_id = ? AND week_start = ?",
        (account_id, week_start),
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            """UPDATE weekly_reviews
               SET summary = ?, key_wins = ?, key_mistakes = ?,
                   next_week_focus = ?, updated_at = CURRENT_TIMESTAMP
               WHERE account_id = ? AND week_start = ?""",
            (summary, key_wins, key_mistakes, next_week_focus, account_id, week_start),
        )
    else:
        cursor.execute(
            """INSERT INTO weekly_reviews (
                account_id, week_start, week_end, summary, key_wins,
                key_mistakes, next_week_focus, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (account_id, week_start, week_end, summary, key_wins, key_mistakes, next_week_focus),
        )

    conn.commit()
    cursor.execute(
        "SELECT * FROM weekly_reviews WHERE account_id = ? AND week_start = ?",
        (account_id, week_start),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"account_id": account_id, "week_start": week_start, "week_end": week_end,
            "summary": summary, "key_wins": key_wins, "key_mistakes": key_mistakes,
            "next_week_focus": next_week_focus}


def get_weekly_goals(account_id: int, week_start: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM weekly_goals WHERE account_id = ? AND week_start = ? ORDER BY created_at",
        (account_id, week_start),
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
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM weekly_goals WHERE account_id = ? AND week_start = ? AND goal_type = ?",
        (account_id, week_start, goal_type),
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            """UPDATE weekly_goals
               SET target_value = ?, target_label = ?, plan_outline = ?,
                   status = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (target_value, target_label, plan_outline, status, existing[0]),
        )
        goal_id = existing[0]
    else:
        cursor.execute(
            """INSERT INTO weekly_goals (
                account_id, week_start, goal_type, target_value,
                target_label, plan_outline, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (account_id, week_start, goal_type, target_value, target_label, plan_outline, status),
        )
        goal_id = cursor.lastrowid

    conn.commit()
    cursor.execute("SELECT * FROM weekly_goals WHERE id = ?", (goal_id,))
    goal = dict(cursor.fetchone())
    conn.close()
    return goal


# ── Drawing operations ───────────────────────────────────────────────────────


def save_drawing(trade_id: int, drawing_type: str, drawing_data: str, account_id: int = 1, symbol: str = "", timeframe: str = "H1") -> int:
    conn = get_connection()
    cursor = conn.cursor()

    try:
        data = json.loads(drawing_data) if isinstance(drawing_data, str) else drawing_data
    except Exception:
        data = {"raw": drawing_data}

    points_json = json.dumps(data.get("points", []))
    style_json = json.dumps(data.get("style", {}))
    note = data.get("note", "")

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
        (account_id, trade_id, "manual_web", symbol, timeframe,
         drawing_type, points_json, style_json, note,
         datetime.now(timezone.utc).isoformat()),
    )
    drawing_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return drawing_id


def get_drawings_for_trade(trade_id: int) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM drawings WHERE trade_id = ? ORDER BY created_at", (trade_id,))
    drawings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return drawings


# ── Monte Carlo operations ───────────────────────────────────────────────────


def save_monte_carlo_run(
    account_id: int,
    num_simulations: int,
    num_trades: int,
    initial_balance: float,
    results: str,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO monte_carlo_runs (
            account_id, num_simulations, num_trades, initial_balance, results
        ) VALUES (?, ?, ?, ?, ?)""",
        (account_id, num_simulations, num_trades, initial_balance, results),
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
        result = dict(row)
        result["results"] = json.loads(result["results"])
        return result

    return {"num_simulations": 0, "num_trades": 0, "initial_balance": 0, "results": {}}


# ── Pine webhook operations ──────────────────────────────────────────────────


def record_pine_webhook(idempotency_key: str, payload: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO pine_webhook_events (idempotency_key, payload) VALUES (?, ?)",
            (idempotency_key, payload),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


# ── Trade lookups ────────────────────────────────────────────────────────────


def find_trade_by_external_id(external_id: str, provider: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    trade_columns = _table_columns(conn, "trades")
    ext_col = "external_id" if "external_id" in trade_columns else "external_trade_id"
    provider_col = "provider" if "provider" in trade_columns else "source"
    cursor.execute(
        f"SELECT * FROM trades WHERE {ext_col} = ? AND {provider_col} = ?",
        (external_id, provider),
    )
    row = cursor.fetchone()
    conn.close()
    return _normalize_trade_row(dict(row)) if row else None


def find_open_trade_by_symbol(account_id: int, symbol: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT * FROM trades
           WHERE account_id = ? AND symbol = ? AND outcome = 'OPEN'
           ORDER BY ts_open DESC LIMIT 1""",
        (account_id, symbol),
    )
    row = cursor.fetchone()
    conn.close()
    return _normalize_trade_row(dict(row)) if row else None


# ── Indicator capture ────────────────────────────────────────────────────────


def capture_indicators_at_timestamp(
    symbol: str,
    asset_type: str,
    timeframe: str,
    timestamp: str,
) -> Dict[str, Optional[float]]:
    import pandas as pd
    from infra.market_data import load_ohlcv_with_cache

    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        start = ts - timedelta(days=30)
        end = ts + timedelta(hours=1)

        df = load_ohlcv_with_cache(
            symbol=symbol, asset_type=asset_type, timeframe=timeframe,
            start=start, end=end, ttl_seconds=0,
        )

        if df.empty:
            return {}

        df['ts'] = pd.to_datetime(df['ts'], utc=True)
        time_diffs = abs(df['ts'] - ts)
        closest_idx = time_diffs.idxmin()
        row = df.loc[closest_idx]

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
