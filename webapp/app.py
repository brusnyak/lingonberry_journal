import json
import os
import sys
import uuid
from html import escape
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import journal_db
from core.exporter import export_ml_dataset
from core.raw_trade_import import parse_raw_trades
from infra.market_data import get_timeframe_for_asset, load_ohlcv_with_cache, replay_window
from infra.pine_bridge import process_pine_payload
from infra.tradelocker_client import get_quote as tl_get_quote, fetch_historical_bars as tl_fetch_bars, subscribe_quotes, TradeLockerError

# ---------------------------------------------------------------------------
# Market structure analysis (imported from pine)
# ---------------------------------------------------------------------------

import pandas as _pd
_PINE_SRC = str(Path(__file__).resolve().parent.parent.parent / "pine" / "backend" / "src")
sys.path.insert(0, _PINE_SRC)

try:
    from features.market_structure import analyze_market_structure as _analyze_structure
    _HAS_STRUCTURE = True
except ImportError:
    _HAS_STRUCTURE = False
# from jobs.sltp_poller import SLTPPoller  # archived

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)  # Enable CORS for all routes

_BLIND_SESSIONS: dict[str, dict] = {}


def _safe_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_ptb_lightning_funded(account: Optional[dict]) -> bool:
    if not account:
        return False
    template = str(account.get("rule_template") or "").lower()
    return template.startswith("plutus_lightning_")


def _build_rule_progress(account: Optional[dict], trades: list[dict], stats: dict) -> dict:
    if not account:
        return {}

    initial_balance = float(account.get("initial_balance") or 0.0)
    closed_trades = [t for t in trades if t.get("outcome") != "OPEN"]
    closed_trades.sort(key=lambda trade: _safe_ts(trade.get("ts_close") or trade.get("ts_open")) or datetime.min.replace(tzinfo=timezone.utc))
    by_day = {}
    current_balance = initial_balance
    lowest_balance = initial_balance
    for trade in closed_trades:
        pnl_usd = float(trade.get("pnl_usd") or 0.0)
        ts_value = trade.get("ts_close") or trade.get("ts_open")
        ts_dt = _safe_ts(ts_value)
        if not ts_dt:
            current_balance += pnl_usd
            lowest_balance = min(lowest_balance, current_balance)
            continue
        day_key = ts_dt.date().isoformat()
        bucket = by_day.setdefault(day_key, {"pnl": 0.0, "count": 0})
        bucket["pnl"] += pnl_usd
        bucket["count"] += 1
        current_balance += pnl_usd
        lowest_balance = min(lowest_balance, current_balance)

    trading_days = len([day for day in by_day.values() if day["count"] > 0])
    profitable_day_threshold_pct = float(account.get("profitable_day_threshold_pct") or 0.0)
    profitable_day_threshold_usd = initial_balance * profitable_day_threshold_pct / 100.0
    profitable_days = len([day for day in by_day.values() if day["pnl"] >= profitable_day_threshold_usd])
    best_day_profit = max((day["pnl"] for day in by_day.values()), default=0.0)
    consistency_pct = float(account.get("consistency_pct") or 0.0)
    minimum_required_profit = 0.0
    if consistency_pct > 0 and best_day_profit > 0:
        minimum_required_profit = best_day_profit / (consistency_pct / 100.0)

    static_drawdown_floor = account.get("static_drawdown_floor")
    if static_drawdown_floor is None and initial_balance and account.get("max_total_loss_pct") is not None:
        static_drawdown_floor = initial_balance * (1 - float(account.get("max_total_loss_pct")) / 100.0)
    static_drawdown_breached = bool(
        static_drawdown_floor is not None and lowest_balance < (float(static_drawdown_floor) - 1e-9)
    )

    daily_loss_state = journal_db.get_daily_loss_state(account, trades)
    current_daily = daily_loss_state.get("current") or {}
    daily_loss_limit = daily_loss_state.get("limit_usd")
    daily_loss_floor = current_daily.get("daily_loss_floor")
    daily_loss_start_balance = current_daily.get("start_balance")
    daily_realized_pnl = current_daily.get("realized_pnl", 0.0)
    daily_loss_used_usd = current_daily.get("current_drawdown_usd", 0.0)
    daily_loss_used_pct = (daily_loss_used_usd / daily_loss_limit * 100.0) if daily_loss_limit else 0.0
    daily_loss_used_account_pct = (daily_loss_used_usd / initial_balance * 100.0) if initial_balance else 0.0
    daily_loss_remaining = current_daily.get("remaining_usd")
    daily_loss_breached = bool(current_daily.get("breached"))
    historical_daily_loss_breached = bool(daily_loss_state.get("has_historical_breach"))

    payout_target_pct = float(account.get("profit_target_pct") or 0.0)
    payout_target_balance = initial_balance * (1 + payout_target_pct / 100.0) if payout_target_pct else None
    current_profit = current_balance - initial_balance
    payout_target_profit = (payout_target_balance - initial_balance) if payout_target_balance is not None else None
    payout_progress_pct = (
        max(0.0, min(100.0, current_profit / payout_target_profit * 100.0))
        if payout_target_profit and payout_target_profit > 0
        else 0.0
    )
    inactivity_limit_days = int(account.get("inactivity_limit_days") or 0)
    last_trade_dt = max((_safe_ts(t.get("ts_close") or t.get("ts_open")) for t in closed_trades), default=None)
    inactive_days = (datetime.now(timezone.utc).date() - last_trade_dt.date()).days if last_trade_dt else None
    inactivity_remaining_days = (
        max(0, inactivity_limit_days - (inactive_days or 0))
        if inactivity_limit_days
        else None
    )

    consistency_met = minimum_required_profit <= 0 or current_profit >= (minimum_required_profit - 1e-9)

    payout_missing_requirements = []
    if _is_ptb_lightning_funded(account):
        if trading_days < 7:
            payout_missing_requirements.append(f"Need {7 - trading_days} more trading day(s)")
        if profitable_days < 7:
            payout_missing_requirements.append(f"Need {7 - profitable_days} more profitable day(s) above 0.5%")
        if payout_target_balance is not None and current_balance < payout_target_balance:
            payout_missing_requirements.append(
                f"Need {(payout_target_balance - current_balance):.2f} more {account.get('currency') or 'USD'} to reach 7% target"
            )
        if not consistency_met:
            payout_missing_requirements.append(
                f"Consistency rule still needs {(minimum_required_profit - current_profit):.2f} more {account.get('currency') or 'USD'}"
            )
        if static_drawdown_breached:
            payout_missing_requirements.append("Static drawdown floor was breached")
        if historical_daily_loss_breached:
            payout_missing_requirements.append("Daily loss floor was breached")
        if inactivity_limit_days and inactive_days is not None and inactive_days > inactivity_limit_days:
            payout_missing_requirements.append("Inactivity limit exceeded")

    is_ptb_lightning = _is_ptb_lightning_funded(account)
    payout_ready = is_ptb_lightning and not payout_missing_requirements

    return {
        "template": account.get("rule_template"),
        "is_ptb_lightning_funded": is_ptb_lightning,
        "currency": account.get("currency") or "USD",
        "trading_days": trading_days,
        "min_trading_days": int(account.get("min_trading_days") or 0),
        "trading_days_remaining": max(0, int(account.get("min_trading_days") or 0) - trading_days),
        "profitable_days": profitable_days,
        "min_profitable_days": int(account.get("min_profitable_days") or 0),
        "profitable_days_remaining": max(0, int(account.get("min_profitable_days") or 0) - profitable_days),
        "profitable_day_threshold_pct": profitable_day_threshold_pct,
        "profitable_day_threshold_usd": profitable_day_threshold_usd,
        "best_day_profit": best_day_profit,
        "best_profitable_day": best_day_profit,
        "consistency_pct": consistency_pct,
        "minimum_required_profit": minimum_required_profit,
        "consistency_met": consistency_met,
        "payout_target_pct": payout_target_pct,
        "payout_target_balance": payout_target_balance,
        "payout_target_profit": payout_target_profit,
        "payout_progress_pct": payout_progress_pct,
        "static_drawdown_floor": static_drawdown_floor,
        "static_drawdown_breached": static_drawdown_breached,
        "static_drawdown_remaining": (current_balance - static_drawdown_floor) if static_drawdown_floor is not None else None,
        "daily_loss_limit": daily_loss_limit,
        "daily_loss_floor": daily_loss_floor,
        "daily_loss_start_balance": daily_loss_start_balance,
        "daily_realized_pnl": daily_realized_pnl,
        "daily_loss_used_usd": daily_loss_used_usd,
        "daily_loss_used_pct": daily_loss_used_pct,
        "daily_loss_used_account_pct": daily_loss_used_account_pct,
        "daily_loss_remaining": daily_loss_remaining,
        "daily_loss_breached": daily_loss_breached,
        "historical_daily_loss_breached": historical_daily_loss_breached,
        "daily_loss_history": daily_loss_state.get("history", []),
        "inactive_days": inactive_days,
        "inactivity_limit_days": inactivity_limit_days,
        "inactivity_remaining_days": inactivity_remaining_days,
        "current_balance": current_balance,
        "current_profit": current_profit,
        "daily_pnl": float(stats.get("daily_pnl") or 0.0),
        "payout_readiness": {
            "eligible": payout_ready if is_ptb_lightning else None,
            "status": "Eligible" if payout_ready else ("Not eligible" if is_ptb_lightning else "Not applicable"),
            "missing_requirements": payout_missing_requirements if is_ptb_lightning else [],
        },
    }


def _parse_account_id(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        abort(400, description="Invalid account_id")


def _default_week_start_iso() -> str:
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.date().isoformat()


def _dashboard_payload(account_id: Optional[int], from_ts: Optional[str], to_ts: Optional[str]) -> dict:
    account = journal_db.get_account(account_id) if account_id else None
    stats = journal_db.get_stats(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    trades = journal_db.get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    rule_trades = journal_db.get_all_trades(account_id=account_id) if account_id else trades
    open_trades = [t for t in trades if t["outcome"] == "OPEN"]
    closed = [t for t in trades if t["outcome"] != "OPEN"]

    equity = []
    balance = stats["initial_balance"]
    equity.append({"ts": None, "balance": balance})
    for t in sorted(closed, key=lambda x: x["ts_close"] or ""):
        balance += t["pnl_usd"] or 0
        equity.append({"ts": t["ts_close"], "balance": balance})

    by_session = {}
    by_symbol = {}
    by_outcome = {"TP": 0, "SL": 0, "MANUAL": 0}
    for t in closed:
        session = t.get("session") or "Unknown"
        by_session[session] = by_session.get(session, 0) + 1
        symbol = t["symbol"]
        by_symbol[symbol] = by_symbol.get(symbol, 0) + (t.get("pnl_pct") or 0)
        if t["outcome"] in by_outcome:
            by_outcome[t["outcome"]] += 1

    calendar = {}
    for t in closed:
        if t.get("ts_close"):
            day = t["ts_close"][:10]
            calendar[day] = calendar.get(day, 0.0) + float(t.get("pnl_usd") or 0.0)

    # Advanced Directional Analytics
    direction_stats = journal_db.get_analytics_breakdown(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    
    monte_carlo = journal_db.get_monte_carlo_stats(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    results = monte_carlo.get("results") or {}
    monte_carlo["simulations"] = results.get("simulations") or [[stats["balance"] for _ in range(10)]]
    monte_carlo["stats"] = results.get("stats") or {"prob_positive": 0.0}

    return {
        "stats": stats,
        "equity": equity,
        "open_trades": open_trades,
        "trades": sorted(trades, key=lambda x: x["ts_open"], reverse=True),
        "calendar": calendar,
        "analytics": direction_stats,
        "monte_carlo": monte_carlo,
        "rule_progress": _build_rule_progress(account, rule_trades, stats),
        "distributions": {
            "session": by_session,
            "symbol_pnl": by_symbol,
            "outcome": by_outcome,
        },
    }


@app.route("/")
def index():
    journal_db.init_db()
    accounts = journal_db.get_accounts()
    account_id = _parse_account_id(request.args.get("account_id"))
    selected = account_id or (accounts[0]["id"] if accounts else None)
    payload = _dashboard_payload(selected, request.args.get("from"), request.args.get("to"))
    return render_template(
        "index.html",
        accounts=accounts,
        selected_account_id=selected,
        payload_json=json.dumps(payload),
        now=datetime.now().strftime("%d %b %Y"),
    )


@app.route("/mini")
def mini_app():
    """Telegram Mini App - lightweight mobile dashboard"""
    journal_db.init_db()
    return render_template("mini.html")


@app.route("/analytics")
def analytics_page():
    """Advanced analytics page"""
    journal_db.init_db()
    return render_template("analytics.html")


@app.route("/weekly")
def weekly_page():
    """Weekly review page - client-side rendered"""
    return render_template("weekly.html")


@app.route("/entry")
def entry_page():
    """Standalone Chart-First Trade Entry page"""
    journal_db.init_db()
    return render_template("trade_entry.html")


@app.route("/charts/<path:filename>")
def serve_chart(filename):
    """Serve generated chart images"""
    import os
    charts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reports")
    return send_from_directory(charts_dir, filename)


@app.route("/backtest")
def backtest_page():
    """Structure analysis backtest page"""
    return render_template("backtest.html")


@app.route("/reports")
def reports_page():
    journal_db.init_db()
    calendar = _dashboard_payload(
        account_id=_parse_account_id(request.args.get("account_id")),
        from_ts=request.args.get("from"),
        to_ts=request.args.get("to"),
    )["calendar"]
    now = datetime.now()
    return render_template(
        "reports.html",
        calendar_json=json.dumps(calendar),
        month_label=now.strftime("%B %Y"),
        now=now.strftime("%d %b %Y"),
    )


@app.route("/api/accounts")
def api_accounts():
    return jsonify(journal_db.get_accounts())


@app.route("/api/accounts", methods=["POST"])
def api_accounts_create():
    body = request.get_json(force=True, silent=True) or {}
    required = ["name", "currency", "initial_balance"]
    if any(k not in body for k in required):
        abort(400, description=f"required keys: {required}")
    account_id = journal_db.create_account(
        name=body["name"],
        currency=body["currency"],
        initial_balance=float(body["initial_balance"]),
        max_daily_loss_pct=float(body.get("max_daily_loss_pct", 5)),
        max_total_loss_pct=float(body.get("max_total_loss_pct", 10)),
        profit_target_pct=float(body.get("profit_target_pct", 10)),
        risk_per_trade_pct=float(body.get("risk_per_trade_pct", 1)),
        firm_name=body.get("firm_name", ""),
        broker=body.get("broker", ""),
        platform=body.get("platform", ""),
        rule_template=body.get("rule_template"),
        consistency_pct=float(body["consistency_pct"]) if body.get("consistency_pct") is not None else None,
        min_trading_days=int(body["min_trading_days"]) if body.get("min_trading_days") is not None else None,
        min_profitable_days=int(body["min_profitable_days"]) if body.get("min_profitable_days") is not None else None,
        profitable_day_threshold_pct=float(body["profitable_day_threshold_pct"]) if body.get("profitable_day_threshold_pct") is not None else None,
        static_drawdown_floor=float(body["static_drawdown_floor"]) if body.get("static_drawdown_floor") is not None else None,
        inactivity_limit_days=int(body["inactivity_limit_days"]) if body.get("inactivity_limit_days") is not None else None,
        payout_frequency_days=int(body["payout_frequency_days"]) if body.get("payout_frequency_days") is not None else None,
        timezone_name=body.get("timezone", "UTC"),
    )
    return jsonify({"account_id": account_id, "account": journal_db.get_account(account_id)}), 201


@app.route("/api/candles")
def api_candles():
    symbol = request.args.get("symbol")
    asset_type = request.args.get("asset_type")
    timeframe = request.args.get("timeframe", "H1")
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    if not symbol:
        return jsonify({"error": "Symbol is required"}), 400
    
    # Auto-detect asset_type if not provided
    if not asset_type:
        symbol_upper = symbol.upper()
        if symbol_upper in ['XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD']:
            asset_type = 'commodity'
        elif symbol_upper in ['US100', 'NAS100', 'SPX500', 'US30']:
            asset_type = 'index'
        elif symbol_upper.startswith('BTC') or symbol_upper.startswith('ETH'):
            asset_type = 'crypto'
        else:
            asset_type = 'forex'

    try:
        # Get current time once for consistent rounding
        now_utc = datetime.now(timezone.utc)

        # Determine 'end' timestamp
        if end_str:
            end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        else:
            # Round down to nearest 5 minutes for effective caching
            end = now_utc.replace(minute=now_utc.minute - (now_utc.minute % 5), second=0, microsecond=0)
            
        # Determine 'start' timestamp
        if start_str:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        else:
            # Calculate start based on the determined 'end'
            start = end - timedelta(days=7)
    except Exception as e:
        return jsonify({"error": f"Invalid date format: {e}"}), 400

    import pandas as pd
    df = load_ohlcv_with_cache(
        symbol=symbol,
        asset_type=asset_type,
        timeframe=timeframe,
        start=start,
        end=end,
        ttl_seconds=30  # 30 second cache for rapid updates like TradingView
    )

    if df.empty:
        return jsonify([])

    result = []
    for _, row in df.iterrows():
        candle = {
            "time": int(row["ts"].timestamp()),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0)),
        }
        # Include indicators added by infra.market_data
        for col in df.columns:
            if col.startswith("ema_") or col == "vwap":
                val = row[col]
                candle[col] = float(val) if pd.notnull(val) else None
        result.append(candle)

    return jsonify(result)


@app.route("/api/market-data")
def api_market_data():
    return api_candles()


# ---------------------------------------------------------------------------
# TradeLocker endpoints
# ---------------------------------------------------------------------------


@app.route("/api/tradelocker/quote")
def api_tl_quote():
    """Get live quote for a symbol from TradeLocker."""
    symbol = request.args.get("symbol", "EURUSD")
    try:
        quote = tl_get_quote(symbol)
        return jsonify({"status": "ok", "symbol": symbol, **quote})
    except TradeLockerError as e:
        return jsonify({"status": "error", "error": str(e)}), 502


@app.route("/api/tradelocker/bars")
def api_tl_bars():
    """Fetch historical bars from TradeLocker."""
    symbol = request.args.get("symbol", "EURUSD")
    timeframe = request.args.get("timeframe", "M15")
    limit = request.args.get("limit", 100, type=int)
    try:
        df = tl_fetch_bars(symbol=symbol, timeframe=timeframe, limit=limit)
        if df.empty:
            return jsonify([])
        bars = []
        for _, row in df.iterrows():
            bars.append({
                "time": int(row["ts"].timestamp()),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
        return jsonify(bars)
    except TradeLockerError as e:
        return jsonify({"status": "error", "error": str(e)}), 502


@app.route("/api/tradelocker/stream")
def api_tl_stream():
    """SSE endpoint for live TradeLocker quotes.

    Streams quote updates via Server-Sent Events.
    Uses the background poller — connects when a client subscribes.
    """
    symbol = request.args.get("symbol", "EURUSD")

    def generate():
        import queue
        q: queue.Queue = queue.Queue(maxsize=10)

        def on_quote(quote):
            try:
                q.put_nowait(quote)
            except queue.Full:
                pass

        subscribe_quotes(symbol, on_quote)

        yield f"data: {{\"status\": \"connected\", \"symbol\": \"{symbol}\"}}\n\n"

        while True:
            try:
                quote = q.get(timeout=30)
                yield f"data: {json.dumps(quote)}\n\n"
            except queue.Empty:
                yield f": keepalive\n\n"

    return app.response_class(generate(), mimetype="text/event-stream")


# ---------------------------------------------------------------------------
# Market structure analysis
# ---------------------------------------------------------------------------


def _df_from_candle_api(symbol: str, asset_type: str, timeframe: str, start: datetime, end: datetime) -> _pd.DataFrame:
    """Load OHLC data and return as DataFrame with DatetimeIndex (for structure analysis)."""
    df = load_ohlcv_with_cache(symbol, asset_type, timeframe, start, end, ttl_seconds=0)
    if df.empty:
        return df
    df = df.copy()
    df["ts"] = _pd.to_datetime(df["ts"], utc=True)
    df = df.set_index("ts")
    df.index.name = None
    df.columns = [c.lower() for c in df.columns]
    df.index = _pd.to_datetime(df.index)
    return df


@app.route("/api/analysis/structure")
def api_structure_analysis():
    """Run market structure analysis on OHLC data.

    Query params:
        symbol (str): Symbol (EURUSD, XAUUSD)
        timeframe (str): M5, M15, H1, H4
        days (int): Lookback days (default 7)
    """
    if not _HAS_STRUCTURE:
        return jsonify({"error": "Market structure module not available (pine backend not found)"}), 503

    symbol = request.args.get("symbol", "EURUSD")
    asset_type = request.args.get("asset_type", "forex")
    timeframe = request.args.get("timeframe", "M5")
    lookback_days = request.args.get("days", 7, type=int)
    swing_period = request.args.get("swing_period", 5, type=int)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)

    df = _df_from_candle_api(symbol, asset_type, timeframe, start, end)
    if df.empty:
        return jsonify({"error": f"No data for {symbol} {timeframe}"}), 404

    try:
        structure = _analyze_structure(
            df,
            swing_period=swing_period,
            break_type="body",
            fvg_mitigation="partial",
            fvg_mitigation_threshold=0.382,
            fvg_min_gap_pct=0.5,
            fvg_min_gap_atr=0.3,
            volume_filter=False,
            detect_amd=False,
        )
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {e}"}), 500

    # Convert structure components to serializable format
    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "bar_count": len(df),
        "date_range": {
            "start": df.index[0].isoformat(),
            "end": df.index[-1].isoformat(),
        },
        "swing_highs": [
            {"time": int(s.time.timestamp()), "price": s.price, "index": s.index}
            for s in structure.get("swing_highs", [])
        ],
        "swing_lows": [
            {"time": int(s.time.timestamp()), "price": s.price, "index": s.index}
            for s in structure.get("swing_lows", [])
        ],
        "structure_labels": [],
        "structure_breaks": [],
        "fvgs": [],
        "order_blocks": [],
        "liquidity_levels": [],
        "liquidity_sweeps": [],
    }

    # Structure labels (HH/HL/LL/LH)
    for label in structure.get("structure_labels", []):
        result["structure_labels"].append({
            "time": int(label.time.timestamp()),
            "price": label.price,
            "label": label.label,
            "type": label.type,
        })

    # Structure breaks (BOS/CHOCH)
    for brk in structure.get("structure_breaks", []):
        result["structure_breaks"].append({
            "time": int(brk.time.timestamp()),
            "price": brk.price,
            "type": brk.type,
            "direction": brk.direction,
        })

    # FVGs
    for fvg in structure.get("fvgs", []):
        result["fvgs"].append({
            "type": fvg.type,
            "top": fvg.top,
            "bottom": fvg.bottom,
            "start_time": int(fvg.start_time.timestamp()) if hasattr(fvg, "start_time") else None,
            "end_time": int(fvg.end_time.timestamp()) if hasattr(fvg, "end_time") else None,
            "mitigated": fvg.mitigated,
        })

    # Order blocks
    for ob in structure.get("order_blocks", []):
        result["order_blocks"].append({
            "type": ob.type,
            "top": ob.top,
            "bottom": ob.bottom,
            "time": int(ob.time.timestamp()) if hasattr(ob, "time") else None,
            "mitigated": ob.mitigated,
        })

    # Liquidity levels
    for liq in structure.get("liquidity_levels", []):
        result["liquidity_levels"].append({
            "type": liq.type,
            "price": liq.price,
            "time": int(liq.time.timestamp()) if hasattr(liq, "time") else None,
            "swept": liq.swept,
        })

    # Liquidity sweeps
    for swp in structure.get("liquidity_sweeps", []):
        result["liquidity_sweeps"].append({
            "time": int(swp.sweep_time.timestamp()) if hasattr(swp, "sweep_time") else None,
            "price": swp.price,
            "type": swp.type,
            "reclaim": swp.reclaim,
            "wick_only": swp.wick_only,
        })

    return jsonify(result)


@app.route("/api/analysis/structure/visualize")
def api_structure_visualize():
    """Return structure data and the candle data in one call (for chart rendering)."""
    symbol = request.args.get("symbol", "EURUSD")
    asset_type = request.args.get("asset_type", "forex")
    timeframe = request.args.get("timeframe", "M5")
    lookback_days = request.args.get("days", 3, type=int)
    swing_period = request.args.get("swing_period", 5, type=int)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)

    # Get candles
    df = _df_from_candle_api(symbol, asset_type, timeframe, start, end)
    if df.empty:
        return jsonify({"error": f"No data for {symbol} {timeframe}"}), 404

    candles = []
    for ts, row in df.iterrows():
        candles.append({
            "time": int(ts.timestamp()),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })

    # Run structure analysis
    try:
        structure = _analyze_structure(
            df,
            swing_period=swing_period,
            break_type="body",
            fvg_mitigation="partial",
            fvg_mitigation_threshold=0.382,
            fvg_min_gap_pct=0.5,
            fvg_min_gap_atr=0.3,
            volume_filter=False,
            detect_amd=False,
        )
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {e}"}), 500

    # Serialise
    def _ts(obj, attr):
        v = getattr(obj, attr, None)
        return int(v.timestamp()) if v is not None else None

    result = {
        "candles": candles,
        "swing_highs": [{"time": _ts(s, "time"), "price": s.price} for s in structure.get("swing_highs", [])],
        "swing_lows": [{"time": _ts(s, "time"), "price": s.price} for s in structure.get("swing_lows", [])],
        "structure_labels": [{"time": _ts(l, "time"), "price": l.price, "label": l.label, "type": l.type} for l in structure.get("structure_labels", [])],
        "structure_breaks": [{"time": _ts(b, "time"), "price": b.price, "type": b.type, "direction": b.direction} for b in structure.get("structure_breaks", [])],
        "fvgs": [{"type": f.type, "top": f.top, "bottom": f.bottom, "start_time": _ts(f, "start_time"), "end_time": _ts(f, "end_time"), "mitigated": f.mitigated} for f in structure.get("fvgs", [])],
        "order_blocks": [{"type": ob.type, "top": ob.top, "bottom": ob.bottom, "time": _ts(ob, "time"), "mitigated": ob.mitigated} for ob in structure.get("order_blocks", [])],
        "liquidity_levels": [{"type": liq.type, "price": liq.price, "time": _ts(liq, "time"), "swept": liq.swept} for liq in structure.get("liquidity_levels", [])],
        "liquidity_sweeps": [{"time": _ts(sw, "sweep_time"), "price": sw.price, "type": sw.type, "reclaim": sw.reclaim, "wick_only": sw.wick_only} for sw in structure.get("liquidity_sweeps", [])],
    }

    return jsonify(result)


# ---------------------------------------------------------------------------


@app.route("/api/trades/manual", methods=["POST"])
def api_trades_manual():
    """Manual trade entry with comprehensive error handling"""
    try:
        body = request.get_json(force=True, silent=True) or {}
        
        # Validate required fields - make ts_close optional since we calculate it
        required = ["symbol", "entry_price", "ts_open"]
        missing = [k for k in required if k not in body]
        if missing:
            return jsonify({
                "error": "Missing required fields",
                "missing_fields": missing,
                "required_fields": required
            }), 400
        
        # Parse and validate account_id
        account_id = _parse_account_id(request.args.get("account_id"))
        if not account_id:
            # Try to get from body or default to 1
            account_id = int(body.get("account_id", 1))
        
        # Validate account exists
        account = journal_db.get_account(account_id)
        if not account:
            return jsonify({
                "error": "Account not found",
                "account_id": account_id
            }), 404
        
        # Parse timestamps - handle both unix timestamps and ISO strings
        try:
            if isinstance(body["ts_open"], (int, float)):
                ts_open = datetime.fromtimestamp(body["ts_open"], timezone.utc).isoformat()
            else:
                ts_open = body["ts_open"]
                
            # ts_close is optional - if not provided, use ts_open (will be updated when trade closes)
            if "ts_close" in body and body["ts_close"]:
                if isinstance(body["ts_close"], (int, float)):
                    ts_close = datetime.fromtimestamp(body["ts_close"], timezone.utc).isoformat()
                else:
                    ts_close = body["ts_close"]
            else:
                # Default to ts_open for now (trade is still open)
                ts_close = ts_open
        except (ValueError, OSError) as e:
            return jsonify({
                "error": "Invalid timestamp format",
                "details": str(e)
            }), 400
        
        # Parse and validate prices
        try:
            entry = float(body["entry_price"])
            lots = float(body.get("lots", 0.1))
            sl_price = float(body["sl"]) if body.get("sl") else None
            tp_price = float(body["tp"]) if body.get("tp") else None
            
            # exit_price is optional - if not provided, trade is still open
            exit_price = float(body["exit_price"]) if body.get("exit_price") else None
        except (ValueError, TypeError) as e:
            return jsonify({
                "error": "Invalid price or lot size",
                "details": str(e)
            }), 400
        
        # Determine direction - prefer explicit direction from body
        direction = body.get("direction")
        if not direction:
            # Infer from entry/tp/sl if not provided
            if tp_price and sl_price:
                direction = "LONG" if tp_price > entry else "SHORT"
            elif exit_price:
                direction = "LONG" if exit_price > entry else "SHORT"
            else:
                return jsonify({
                    "error": "Cannot determine direction",
                    "message": "Please provide direction, or both TP and SL prices"
                }), 400
        direction = direction.upper()
        
        if direction not in ["LONG", "SHORT"]:
            return jsonify({
                "error": "Invalid direction",
                "direction": direction,
                "valid_values": ["LONG", "SHORT"]
            }), 400
        
        # Determine outcome - default to OPEN if no exit price
        outcome = body.get("outcome")
        if not outcome:
            if exit_price:
                # Infer outcome based on direction and exit price
                if direction == "LONG":
                    outcome = "TP" if exit_price > entry else "SL"
                else:
                    outcome = "TP" if exit_price < entry else "SL"
            else:
                outcome = "OPEN"  # Trade is still open
        
        # Extract metadata
        is_perfect = body.get("is_perfect", False)
        week_start = body.get("week_start")
        
        # Auto-calculate week_start if not provided
        if not week_start:
            ts_open_dt = datetime.fromisoformat(ts_open.replace('Z', '+00:00'))
            day_of_week = ts_open_dt.weekday()  # Monday = 0, Sunday = 6
            days_since_monday = day_of_week
            monday = ts_open_dt - timedelta(days=days_since_monday)
            week_start = monday.strftime('%Y-%m-%d')
        
        notes = body.get("notes", "")
        symbol = body["symbol"]
        asset_type = body.get("asset_type", "forex")
        timeframe = body.get("timeframe", "M30")
        
        # Auto-detect asset type if not provided
        if not body.get("asset_type"):
            symbol_upper = symbol.upper()
            if symbol_upper in ["NAS100", "US100", "USTEC", "SPX500", "US30", "GER30", "UK100"]:
                asset_type = "index"
            elif symbol_upper in ["XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "USOIL", "UKOIL"]:
                asset_type = "commodity"
            elif symbol_upper.startswith("BTC") or symbol_upper.startswith("ETH"):
                asset_type = "crypto"
            else:
                asset_type = "forex"
        
        # Build indicator_data from various sources
        indicator_data = body.get("indicator_data", {})
        if not isinstance(indicator_data, dict):
            indicator_data = {}
        
        # Capture indicators at entry timestamp
        try:
            entry_indicators = journal_db.capture_indicators_at_timestamp(
                symbol=symbol,
                asset_type=asset_type,
                timeframe=timeframe,
                timestamp=ts_open
            )
            if entry_indicators:
                indicator_data["entry"] = entry_indicators
                print(f"✅ Captured entry indicators for {symbol} at {ts_open}")
        except Exception as e:
            print(f"⚠️ Failed to capture entry indicators: {e}")
        
        # Capture indicators at exit timestamp if trade is closed
        if exit_price and ts_close and ts_close != ts_open:
            try:
                exit_indicators = journal_db.capture_indicators_at_timestamp(
                    symbol=symbol,
                    asset_type=asset_type,
                    timeframe=timeframe,
                    timestamp=ts_close
                )
                if exit_indicators:
                    indicator_data["exit"] = exit_indicators
                    print(f"✅ Captured exit indicators for {symbol} at {ts_close}")
            except Exception as e:
                print(f"⚠️ Failed to capture exit indicators: {e}")
        
        # Add additional fields to indicator_data
        for key in ["mindset", "setup", "risk"]:
            if key in body:
                indicator_data[key] = body[key]
        
        # 1. Save trade to database
        # If exit_price is None, use TP as placeholder for closed trade calculation
        effective_exit = exit_price if exit_price is not None else (tp_price if outcome == "TP" else sl_price)
        
        trade_id = journal_db.add_manual_trade(
            account_id=account_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry,
            exit_price=effective_exit,
            sl_price=sl_price,
            tp_price=tp_price,
            ts_open=ts_open,
            ts_close=ts_close,
            lots=lots,
            asset_type=asset_type,
            timeframe=timeframe,
            notes=notes,
            outcome=outcome,
            indicator_data=indicator_data if indicator_data else None
        )
        
        # 2. Update additional fields (is_perfect, week_start)
        if is_perfect or week_start:
            conn = journal_db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE trades SET is_perfect = ?, week_start = ? WHERE id = ?",
                (1 if is_perfect else 0, week_start, trade_id)
            )
            conn.commit()
            conn.close()
        
        # 3. Save drawings if provided
        drawings = body.get("drawings", [])
        if drawings and not isinstance(drawings, list):
            drawings = [drawings]
        
        saved_drawings = []
        for drw in drawings:
            try:
                drawing_id = journal_db.save_drawing(
                    trade_id=trade_id,
                    drawing_type=drw.get("type", "unknown"),
                    drawing_data=json.dumps(drw),
                    account_id=account_id,
                    symbol=symbol,
                    timeframe=body.get("timeframe", "H1")
                )
                saved_drawings.append(drawing_id)
            except Exception as e:
                print(f"Warning: Failed to save drawing: {e}")
                # Continue even if drawing save fails
        
        # 4. Save user screenshot if provided (primary chart)
        chart_paths = []
        chart_screenshot = body.get("chart_screenshot")
        
        if chart_screenshot:
            try:
                import base64
                
                # Extract base64 data
                if ',' in chart_screenshot:
                    chart_screenshot = chart_screenshot.split(',')[1]
                
                # Decode and save
                charts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reports")
                os.makedirs(charts_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"trade_{symbol}_{direction}_{timeframe}_{timestamp}.jpg"
                filepath = os.path.join(charts_dir, filename)
                
                # Decode base64
                screenshot_data = base64.b64decode(chart_screenshot)
                
                with open(filepath, 'wb') as f:
                    f.write(screenshot_data)
                
                chart_paths = [filepath]
                
                print(f"✅ Screenshot saved for trade {trade_id}: {filename} ({len(screenshot_data)} bytes)")
                
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"⚠️ Screenshot save failed for trade {trade_id}: {e}")
                print(error_trace)
                # Don't fail the request if screenshot save fails
        else:
            print(f"ℹ️ No screenshot provided for trade {trade_id}")
        
        return jsonify({
            "success": True,
            "trade_id": trade_id,
            "charts": [os.path.basename(p) for p in chart_paths] if chart_paths else [],
            "drawings_saved": len(saved_drawings),
            "message": "Trade saved successfully" + (f" with {len(chart_paths)} charts" if chart_paths else "")
        }), 201
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error in api_trades_manual: {error_trace}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e),
            "type": type(e).__name__,
            "trace": error_trace.split('\n')[-10:]  # Last 10 lines of trace
        }), 500


@app.route("/api/trades/import_raw", methods=["POST"])
def api_trades_import_raw():
    """Import raw trade logs (platform or prop firm) and store as manual trades."""
    try:
        body = request.get_json(force=True, silent=True) or {}
        raw_text = body.get("text", "")
        if not raw_text.strip():
            return jsonify({"error": "Missing raw trade text"}), 400

        account_ids = body.get("account_ids", [])
        if not account_ids: # If account_ids list is empty, try single account_id
            single_account_id = _parse_account_id(request.args.get("account_id"))
            if not single_account_id:
                single_account_id = int(body.get("account_id", 1))
            account_ids = [single_account_id]
        
        # Filter out None values and ensure all are integers
        account_ids = [int(aid) for aid in account_ids if aid is not None]
        
        if not account_ids:
            return jsonify({"error": "No account_id(s) provided"}), 400

        # Verify all accounts exist
        for aid in account_ids:
            account = journal_db.get_account(aid)
            if not account:
                return jsonify({"error": f"Account not found: {aid}"}), 404

        tz_offset = int(body.get("timezone_offset_hours", 2))
        timeframe = body.get("timeframe", "M30")

        trades = parse_raw_trades(raw_text, tz_offset_hours=tz_offset)
        if not trades:
            return jsonify({"error": "No trades parsed from input"}), 400

        imported = []
        skipped = 0
        already_existed = 0
        
        for aid in account_ids:
            for t in trades:
                try:
                    trade_id = journal_db.create_trade(
                        account_id=aid,
                        symbol=t["symbol"],
                        direction=t["direction"],
                        entry_price=t["entry_price"],
                        position_size=t.get("lots", 0.1),
                        ts_open=t["ts_open"],
                        sl_price=t.get("sl"),
                        tp_price=t.get("tp"),
                        timeframe=timeframe,
                        notes=t.get("notes"),
                        external_id=t.get("external_id"),
                        provider="import_api",
                    )

                    if trade_id is None:
                        already_existed += 1
                        continue

                    journal_db.close_trade(
                        trade_id=trade_id,
                        exit_price=t["exit_price"],
                        outcome=t.get("outcome", "MANUAL"),
                        event_type="import",
                        provider="import_api",
                        payload=t,
                        ts_close=t.get("ts_close"),
                        pnl_usd_override=t.get("pnl_usd"),
                    )

                    imported.append({
                        "trade_id": trade_id,
                        "account_id": aid,
                        "symbol": t["symbol"],
                        "ts_open": t["ts_open"],
                    })
                except Exception as e:
                    print(f"⚠️ Error importing trade: {e}")
                    skipped += 1

        return jsonify({
            "imported": imported,
            "imported_count": len(imported),
            "skipped": skipped,
            "already_existed": already_existed,
        })
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error in api_trades_import_raw: {error_trace}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/api/accounts/<int:account_id>", methods=["PUT"])
def api_account_update(account_id: int):
    body = request.get_json(force=True, silent=True) or {}
    
    # Update account basic info
    conn = journal_db.get_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if "name" in body:
        updates.append("name = ?")
        params.append(body["name"])
    if "currency" in body:
        updates.append("currency = ?")
        params.append(body["currency"])
    if "initial_balance" in body:
        updates.append("initial_balance = ?")
        params.append(float(body["initial_balance"]))
    if "firm_name" in body:
        updates.append("firm_name = ?")
        params.append(body["firm_name"])
    if "broker" in body:
        updates.append("broker = ?")
        params.append(body["broker"])
    if "platform" in body:
        updates.append("platform = ?")
        params.append(body["platform"])
    if "rule_template" in body:
        updates.append("rule_template = ?")
        params.append(body["rule_template"])
    if "consistency_pct" in body:
        updates.append("consistency_pct = ?")
        params.append(float(body["consistency_pct"]) if body["consistency_pct"] is not None else None)
    if "min_trading_days" in body:
        updates.append("min_trading_days = ?")
        params.append(int(body["min_trading_days"]) if body["min_trading_days"] is not None else None)
    if "min_profitable_days" in body:
        updates.append("min_profitable_days = ?")
        params.append(int(body["min_profitable_days"]) if body["min_profitable_days"] is not None else None)
    if "profitable_day_threshold_pct" in body:
        updates.append("profitable_day_threshold_pct = ?")
        params.append(float(body["profitable_day_threshold_pct"]) if body["profitable_day_threshold_pct"] is not None else None)
    if "static_drawdown_floor" in body:
        updates.append("static_drawdown_floor = ?")
        params.append(float(body["static_drawdown_floor"]) if body["static_drawdown_floor"] is not None else None)
    if "inactivity_limit_days" in body:
        updates.append("inactivity_limit_days = ?")
        params.append(int(body["inactivity_limit_days"]) if body["inactivity_limit_days"] is not None else None)
    if "payout_frequency_days" in body:
        updates.append("payout_frequency_days = ?")
        params.append(int(body["payout_frequency_days"]) if body["payout_frequency_days"] is not None else None)
    
    if updates:
        params.append(account_id)
        cursor.execute(
            f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
    
    # Update rules if provided
    if any(k in body for k in [
        "max_daily_loss_pct",
        "max_total_loss_pct",
        "profit_target_pct",
        "risk_per_trade_pct",
        "consistency_pct",
        "min_trading_days",
        "min_profitable_days",
        "profitable_day_threshold_pct",
        "static_drawdown_floor",
        "inactivity_limit_days",
        "payout_frequency_days",
    ]):
        journal_db.update_account_rules(
            account_id=account_id,
            max_daily_loss_pct=float(body.get("max_daily_loss_pct", 5)),
            max_total_loss_pct=float(body.get("max_total_loss_pct", 10)),
            profit_target_pct=float(body.get("profit_target_pct", 10)),
            risk_per_trade_pct=float(body.get("risk_per_trade_pct", 1)),
            consistency_pct=float(body["consistency_pct"]) if body.get("consistency_pct") is not None else None,
            min_trading_days=int(body["min_trading_days"]) if body.get("min_trading_days") is not None else None,
            min_profitable_days=int(body["min_profitable_days"]) if body.get("min_profitable_days") is not None else None,
            profitable_day_threshold_pct=float(body["profitable_day_threshold_pct"]) if body.get("profitable_day_threshold_pct") is not None else None,
            static_drawdown_floor=float(body["static_drawdown_floor"]) if body.get("static_drawdown_floor") is not None else None,
            inactivity_limit_days=int(body["inactivity_limit_days"]) if body.get("inactivity_limit_days") is not None else None,
            payout_frequency_days=int(body["payout_frequency_days"]) if body.get("payout_frequency_days") is not None else None,
        )
    
    conn.close()
    return jsonify({"account": journal_db.get_account(account_id)})


@app.route("/api/accounts/<int:account_id>", methods=["DELETE"])
def api_account_delete(account_id: int):
    """Delete an account (soft delete - keeps trades)"""
    account = journal_db.get_account(account_id)
    if not account:
        abort(404, description="Account not found")
    
    conn = journal_db.get_connection()
    cursor = conn.cursor()
    
    # Soft delete by setting status to DELETED
    cursor.execute(
        "UPDATE accounts SET status = 'DELETED', updated_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), account_id)
    )
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Account deleted"})


@app.route("/api/accounts/<int:account_id>/rules", methods=["POST"])
def api_account_rules_update(account_id: int):
    body = request.get_json(force=True, silent=True) or {}
    journal_db.update_account_rules(
        account_id=account_id,
        max_daily_loss_pct=float(body.get("max_daily_loss_pct", 5)),
        max_total_loss_pct=float(body.get("max_total_loss_pct", 10)),
        profit_target_pct=float(body.get("profit_target_pct", 10)),
        risk_per_trade_pct=float(body.get("risk_per_trade_pct", 1)),
    )
    return jsonify({"account": journal_db.get_account(account_id)})


@app.route("/api/dashboard")
def api_dashboard():
    account_id = _parse_account_id(request.args.get("account_id"))
    return jsonify(
        _dashboard_payload(
            account_id=account_id,
            from_ts=request.args.get("from"),
            to_ts=request.args.get("to"),
        )
    )


@app.route("/api/trades")
def api_trades():
    account_id = _parse_account_id(request.args.get("account_id"))
    return jsonify(
        journal_db.get_all_trades(
            account_id=account_id,
            from_ts=request.args.get("from"),
            to_ts=request.args.get("to"),
        )
    )


@app.route("/api/trades/<int:trade_id>")
def api_trade(trade_id: int):
    """Get single trade by ID"""
    trade = journal_db.get_trade(trade_id)
    if not trade:
        abort(404, description="Trade not found")
    return jsonify(trade)


@app.route("/api/trades/open")
def api_open_trades():
    account_id = _parse_account_id(request.args.get("account_id"))
    return jsonify(journal_db.get_open_trades(account_id=account_id))


@app.route("/api/trades/<int:trade_id>/events")
def api_trade_events(trade_id: int):
    return jsonify(journal_db.get_trade_events(trade_id))


@app.route("/api/trades/<int:trade_id>/close", methods=["POST"])
def api_trade_close(trade_id: int):
    body = request.get_json(force=True, silent=True) or {}
    if "exit_price" not in body:
        abort(400, description="exit_price is required")
    closed = journal_db.close_trade(
        trade_id=trade_id,
        exit_price=float(body["exit_price"]),
        outcome=body.get("outcome", "MANUAL"),
        event_type="manually_closed",
        provider="api",
        payload={"source": "api_manual_close"},
    )
    if not closed:
        abort(404, description="Trade not found")
    return jsonify(closed)


@app.route("/api/trades/<int:trade_id>/review", methods=["POST"])
def api_trade_review(trade_id: int):
    body = request.get_json(force=True, silent=True) or {}
    try:
        row = journal_db.upsert_trade_review_note(
            trade_id=trade_id,
            reviewer_note=body.get("reviewer_note"),
            should_have_done_entry=body.get("should_have_done_entry"),
            should_have_done_exit=body.get("should_have_done_exit"),
            should_have_done_sl=body.get("should_have_done_sl"),
            should_have_done_tp=body.get("should_have_done_tp"),
            week_start=body.get("week_start"),
        )
    except ValueError as exc:
        abort(404, description=str(exc))
    return jsonify(row)


@app.route("/api/review/week")
def api_week_review():
    account_id = _parse_account_id(request.args.get("account_id")) or 1
    week_start = request.args.get("week_start") or _default_week_start_iso()
    review = journal_db.get_weekly_review(account_id=account_id, week_start=week_start)
    review["goals"] = journal_db.get_weekly_goals(account_id=account_id, week_start=week_start)
    return jsonify(review)


@app.route("/api/review/week", methods=["POST"])
def api_week_review_upsert():
    body = request.get_json(force=True, silent=True) or {}
    if "account_id" not in body or "week_start" not in body:
        abort(400, description="account_id and week_start required")
    row = journal_db.upsert_weekly_review(
        account_id=int(body["account_id"]),
        week_start=body["week_start"],
        summary=body.get("summary"),
        key_wins=body.get("key_wins"),
        key_mistakes=body.get("key_mistakes"),
        next_week_focus=body.get("next_week_focus"),
    )
    return jsonify(row)


@app.route("/api/goals/week", methods=["POST"])
def api_goal_week_upsert():
    body = request.get_json(force=True, silent=True) or {}
    required = ["account_id", "week_start", "goal_type"]
    if any(k not in body for k in required):
        abort(400, description=f"required keys: {required}")
    row = journal_db.upsert_weekly_goal(
        account_id=int(body["account_id"]),
        week_start=body["week_start"],
        goal_type=body["goal_type"],
        target_value=float(body["target_value"]) if body.get("target_value") is not None else None,
        target_label=body.get("target_label"),
        plan_outline=body.get("plan_outline"),
        status=body.get("status", "ACTIVE"),
    )
    return jsonify(row)


@app.route("/api/goals/week")
def api_goal_week_get():
    account_id = _parse_account_id(request.args.get("account_id")) or 1
    week_start = request.args.get("week_start") or _default_week_start_iso()
    return jsonify(journal_db.get_weekly_goals(account_id=account_id, week_start=week_start))
@app.route("/api/trades/week")
def api_trades_week():
    """Get trades for a specific week"""
    account_id = _parse_account_id(request.args.get("account_id"))
    week_start = request.args.get("week_start") or _default_week_start_iso()

    # Parse is_perfect filter
    is_perfect = None
    if request.args.get("is_perfect") == "true":
        is_perfect = True
    elif request.args.get("is_perfect") == "false":
        is_perfect = False

    trades = journal_db.get_trades_by_week(
        week_start=week_start,
        account_id=account_id,
        is_perfect=is_perfect
    )
    return jsonify(trades)


@app.route("/api/trades/week/stats")
def api_trades_week_stats():
    """Get statistics for a specific week"""
    account_id = _parse_account_id(request.args.get("account_id"))
    week_start = request.args.get("week_start") or _default_week_start_iso()

    # Parse is_perfect filter
    is_perfect = None
    if request.args.get("is_perfect") == "true":
        is_perfect = True
    elif request.args.get("is_perfect") == "false":
        is_perfect = False

    stats = journal_db.get_week_stats(
        week_start=week_start,
        account_id=account_id,
        is_perfect=is_perfect
    )
    return jsonify(stats)





@app.route("/api/replay/<int:trade_id>")
def api_replay(trade_id: int):
    trade = journal_db.get_trade(trade_id)
    if not trade:
        abort(404, description="Trade not found")

    context_weeks = int(request.args.get("context_weeks", 1))
    timeframe = request.args.get("timeframe", "auto")
    if timeframe == "auto":
        timeframe = trade.get("timeframe") or get_timeframe_for_asset(trade["asset_type"])

    window = replay_window(trade["ts_open"], context_weeks=context_weeks)
    df = load_ohlcv_with_cache(
        symbol=trade["symbol"],
        asset_type=trade["asset_type"],
        timeframe=timeframe,
        start=window["start"],
        end=window["end"],
    )

    candles = []
    if not df.empty:
        for _, row in df.iterrows():
            candles.append(
                {
                    "ts": row["ts"].isoformat(),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            )

    return jsonify(
        {
            "trade": trade,
            "timeframe": timeframe,
            "window": {"start": window["start"].isoformat(), "end": window["end"].isoformat()},
            "candles": candles,
            "drawings": journal_db.get_drawings_for_trade(trade_id),
        }
    )


# @app.route("/api/jobs/sltp-check", methods=["POST"])
# def api_sltp_check():
#     body = request.get_json(force=True, silent=True) or {}
#     account_id = body.get("account_id")
#     poller = SLTPPoller()
#     result = poller.run_once(account_id=int(account_id) if account_id is not None else None)
#     return jsonify({"closed": result, "count": len(result)})


@app.route("/api/pine/webhook", methods=["POST"])
def api_pine_webhook():
    expected_secret = os.getenv("PINE_WEBHOOK_SECRET")
    provided_secret = request.headers.get("X-Pine-Secret")
    if expected_secret and expected_secret != provided_secret:
        abort(401, description="Invalid webhook secret")

    idempotency_key = request.headers.get("X-Idempotency-Key")
    if not idempotency_key:
        abort(400, description="X-Idempotency-Key header is required")

    payload = request.get_json(force=True, silent=True)
    if not isinstance(payload, dict):
        abort(400, description="JSON object payload required")

    result = process_pine_payload(payload=payload, idempotency_key=idempotency_key)
    return jsonify(result)


@app.route("/api/cache/refresh", methods=["POST"])
def api_cache_refresh():
    body = request.get_json(force=True, silent=True) or {}
    required = ["symbol", "asset_type", "timeframe", "start", "end"]
    if any(k not in body for k in required):
        abort(400, description=f"required keys: {required}")

    start = datetime.fromisoformat(body["start"])
    end = datetime.fromisoformat(body["end"])
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    df = load_ohlcv_with_cache(
        symbol=body["symbol"],
        asset_type=body["asset_type"],
        timeframe=body["timeframe"],
        start=start,
        end=end,
        ttl_seconds=0,
    )
    return jsonify({"rows": len(df), "symbol": body["symbol"], "timeframe": body["timeframe"]})


@app.route("/api/export/ml", methods=["POST"])
def api_export_ml():
    body = request.get_json(force=True, silent=True) or {}
    result = export_ml_dataset(
        account_id=body.get("account_id"),
        from_ts=body.get("from"),
        to_ts=body.get("to"),
    )
    return jsonify(result)


@app.route("/api/analytics/direction-accuracy")
def api_direction_accuracy():
    """Get direction accuracy statistics"""
    account_id = _parse_account_id(request.args.get("account_id"))
    from_ts = request.args.get("from")
    to_ts = request.args.get("to")
    return jsonify(journal_db.get_direction_accuracy_stats(
        account_id=account_id,
        from_ts=from_ts,
        to_ts=to_ts
    ))


@app.route("/api/analytics/analyze-direction", methods=["POST"])
def api_analyze_direction():
    """Analyze direction correctness for trades"""
    body = request.get_json(force=True, silent=True) or {}
    trade_id = body.get("trade_id")
    account_id = body.get("account_id")
    from_ts = body.get("from")
    to_ts = body.get("to")
    
    result = journal_db.analyze_direction_correctness(
        trade_id=trade_id,
        account_id=account_id,
        from_ts=from_ts,
        to_ts=to_ts
    )
    return jsonify(result)


@app.route("/api/analytics/monte-carlo")
def api_monte_carlo():
    account_id = _parse_account_id(request.args.get("account_id"))
    from_ts = request.args.get("from")
    to_ts = request.args.get("to")
    
    try:
        from core.monte_carlo import run_monte_carlo_simulation
        
        results = run_monte_carlo_simulation(
            account_id=account_id or 1,
            num_simulations=100,
            num_trades=50,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        
        if results.get("status") == "error":
            return jsonify({
                "simulations": [],
                "stats": {},
                "error": results.get("message", "Not enough data")
            })
        
        # Generate simulation paths for visualization
        trades = journal_db.get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
        closed_trades = [t for t in trades if t.get("outcome") != "OPEN"]
        pnl_pcts = [t.get("pnl_pct") for t in closed_trades if t.get("pnl_pct") is not None]
        
        if not pnl_pcts:
            return jsonify({
                "simulations": [],
                "stats": {},
                "error": "No trade data available"
            })
        
        # Generate 10 sample paths for visualization
        import random
        simulations = []
        initial_balance = results.get("initial_balance", 10000)
        
        for _ in range(10):
            path = [initial_balance]
            balance = initial_balance
            for _ in range(50):
                pnl_pct = random.choice(pnl_pcts)
                balance += balance * (pnl_pct / 100)
                path.append(balance)
            simulations.append(path)
        
        return jsonify({
            "simulations": simulations,
            "stats": {
                "median_final": results["final_balance"]["median"] - initial_balance,
                "p25_final": results["final_balance"]["percentile_25"] - initial_balance,
                "p75_final": results["final_balance"]["percentile_75"] - initial_balance,
                "prob_profit": results["probability_of_profit"] / 100,
            }
        })
        
    except Exception as e:
        import traceback
        print(f"Monte Carlo error: {traceback.format_exc()}")
        return jsonify({
            "simulations": [],
            "stats": {},
            "error": str(e)
        })



@app.route("/api/trades/<int:trade_id>/playback")
def api_trade_playback(trade_id: int):
    trade = journal_db.get_trade(trade_id)
    if not trade:
        abort(404, description="Trade not found")

    # TODO: wire TradeLocker or local cache for candle fetch
    candles = []
    return jsonify({"trade": trade, "candles": candles})


# ── Visual Backtest Reviewer ──────────────────────────────────────────────────

@app.route("/review")
def review_page():
    return render_template("review.html")


@app.route("/blind")
def blind_review_page():
    return render_template("blind_review.html")


def _review_asset_type(symbol: str) -> str:
    if symbol in ("XAUUSD", "XAGUSD"):
        return "commodity"
    if symbol in ("NAS100", "US100", "USATECHIDXUSD"):
        return "index"
    if symbol in ("BTCUSD", "ETHUSD", "ADAUSDT", "XRPUSDT"):
        return "crypto"
    return "forex"


def _candles_json_from_df(df) -> list[dict]:
    return [
        {
            "time": int(row["ts"].timestamp()),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }
        for _, row in df.iterrows()
    ]


def _tf_minutes(tf: str) -> int:
    return {"1": 1, "5": 5, "15": 15, "30": 30, "60": 60, "240": 240, "1440": 1440}.get(str(tf), 5)


def _blind_public_state(session: dict, cursor: int | None = None, context_bars: int | None = None) -> dict:
    candles = session["candles"]
    indicators = session.get("indicators", {})
    cursor = session["cursor"] if cursor is None else int(cursor)
    context_bars = session["context_bars"] if context_bars is None else int(context_bars)
    cursor = max(0, min(cursor, len(candles) - 1))
    lo = max(0, cursor - context_bars + 1)
    visible = candles[lo: cursor + 1]
    current = candles[cursor]
    return {
        "session_id": session["session_id"],
        "symbol": session["symbol"],
        "tf": session["tf"],
        "cursor": cursor,
        "cursor_time": current["time"],
        "visible_from": visible[0]["time"] if visible else current["time"],
        "visible_to": current["time"],
        "candles": visible,
        "indicators": {name: vals[lo: cursor + 1] for name, vals in indicators.items()},
        "has_prev": cursor > 0,
        "has_next": cursor < len(candles) - 1,
        "total_loaded": len(candles),
        "decisions": len(session.get("decisions", [])),
        "management_events": len(session.get("management_events", [])),
    }


def _blind_store_path() -> Path:
    return Path(__file__).resolve().parent / "blind_decisions.jsonl"


def _blind_append_decision(row: dict) -> None:
    path = _blind_store_path()
    with open(path, "a") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _jsonl_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _value_at_or_before(series: list[dict], ts: int) -> Optional[float]:
    val = None
    for row in series:
        if int(row.get("time", 0)) > ts:
            break
        val = row.get("value")
    return float(val) if val is not None else None


def _indicator_snapshot(session: dict, cursor: int) -> dict:
    ts = int(session["candles"][cursor]["time"])
    return {
        name: _value_at_or_before(vals, ts)
        for name, vals in session.get("indicators", {}).items()
    }


def _indicator_json_from_df(df) -> dict[str, list[dict]]:
    import pandas as pd

    out: dict[str, list[dict]] = {}
    d = df.copy().reset_index(drop=True)
    close = pd.to_numeric(d["close"], errors="coerce")
    for period in (9, 21, 50, 200):
        ema = close.ewm(span=period, adjust=False).mean()
        out[f"ema{period}"] = [
            {"time": int(ts.timestamp()), "value": float(val)}
            for ts, val in zip(d["ts"], ema)
            if pd.notna(val)
        ]

    typical = (d["high"] + d["low"] + d["close"]) / 3.0
    volume = d["volume"] if "volume" in d.columns else pd.Series([1.0] * len(d))
    day = pd.to_datetime(d["ts"], utc=True).dt.date
    pv = typical * volume
    vwap = pv.groupby(day).cumsum() / volume.groupby(day).cumsum().replace(0, float("nan"))
    out["vwap"] = [
        {"time": int(ts.timestamp()), "value": float(val)}
        for ts, val in zip(d["ts"], vwap)
        if pd.notna(val)
    ]

    prev_close = close.shift(1).fillna(close)
    tr = pd.concat(
        [
            d["high"] - d["low"],
            (d["high"] - prev_close).abs(),
            (d["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr14 = tr.ewm(alpha=1 / 14, adjust=False).mean()
    out["atr14"] = [
        {"time": int(ts.timestamp()), "value": float(val)}
        for ts, val in zip(d["ts"], atr14)
        if pd.notna(val)
    ]
    return out


def _load_blind_decision_candles(row: dict, max_bars: int = 288) -> tuple[list[dict], int]:
    import pandas as pd
    from backtesting.engine.data import load_data

    symbol = str(row.get("symbol", "XAUUSD")).upper()
    tf = str(row.get("tf", "5"))
    visible_ts = pd.Timestamp(row.get("visible_until_iso"))
    visible_ts = visible_ts.tz_localize("UTC") if visible_ts.tzinfo is None else visible_ts.tz_convert("UTC")
    minutes = _tf_minutes(tf)
    start = (visible_ts - pd.Timedelta(minutes=minutes)).isoformat()
    end = (visible_ts + pd.Timedelta(minutes=minutes * (max_bars + 4))).isoformat()
    df = load_data(symbol, tf=tf, start=start, end=end, asset_type=_review_asset_type(symbol))
    if df.empty:
        return [], 0
    df = df.sort_values("ts").reset_index(drop=True)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    candles = _candles_json_from_df(df)
    target = int(visible_ts.timestamp())
    cursor = 0
    for i, c in enumerate(candles):
        if int(c["time"]) <= target:
            cursor = i
        else:
            break
    return candles, cursor


def _score_blind_decision(row: dict, max_bars: int = 288) -> dict:
    candles, cursor = _load_blind_decision_candles(row, max_bars=max_bars)
    if not candles:
        return {**row, "score_error": "no candles"}
    if not row.get("entry") or not row.get("sl") or not row.get("tp") or not row.get("direction"):
        return {**row, "score_error": "missing trade plan"}
    try:
        sim = _simulate_blind_plan(
            candles,
            cursor,
            row,
            max_bars=max_bars,
            management_events=row.get("management_events", []),
        )
    except Exception as e:
        return {**row, "score_error": str(e)}
    return {**row, **{f"sim_{k}": v for k, v in sim.items() if k != "revealed_candles"}}


def _blind_analysis_summary(scored: list[dict]) -> dict:
    valid = [r for r in scored if "sim_r_multiple" in r]
    if not valid:
        return {"total": len(scored), "valid": 0}
    rs = [float(r["sim_r_multiple"]) for r in valid]
    wins = [r for r in rs if r > 0]
    by_key = {}
    for r in valid:
        for key in ("symbol", "tf", "bias", "direction"):
            val = str(r.get(key) or "")
            if not val:
                continue
            bucket = by_key.setdefault(f"{key}:{val}", [])
            bucket.append(float(r["sim_r_multiple"]))
    buckets = [
        {
            "bucket": k,
            "n": len(v),
            "avg_r": round(sum(v) / len(v), 3),
            "win_rate": round(sum(1 for x in v if x > 0) / len(v), 3),
        }
        for k, v in by_key.items()
    ]
    buckets.sort(key=lambda x: (x["n"], x["avg_r"]), reverse=True)
    return {
        "total": len(scored),
        "valid": len(valid),
        "win_rate": round(len(wins) / len(valid), 3),
        "avg_r": round(sum(rs) / len(rs), 3),
        "median_r": round(sorted(rs)[len(rs) // 2], 3),
        "best_r": round(max(rs), 3),
        "worst_r": round(min(rs), 3),
        "buckets": buckets[:20],
    }


def _simulate_blind_plan(
    candles: list[dict],
    cursor: int,
    plan: dict,
    max_bars: int = 288,
    management_events: list[dict] | None = None,
) -> dict:
    direction = str(plan.get("direction") or "").lower()
    entry = float(plan.get("entry"))
    sl = float(plan.get("sl"))
    tp = float(plan.get("tp"))
    if direction not in ("long", "short"):
        raise ValueError("direction must be long or short")
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk <= 0 or reward <= 0:
        raise ValueError("entry/sl/tp must define positive risk and reward")

    outcome = "open"
    active_sl = sl
    remaining_frac = 1.0
    banked_r = 0.0
    exit_price = None
    exit_time = None
    exit_cursor = None
    mfe = 0.0
    mae = 0.0
    start = min(cursor + 1, len(candles))
    stop = min(len(candles), start + max(1, max_bars))
    reveal = []
    events = sorted(
        [e for e in (management_events or []) if int(e.get("cursor", -1)) > cursor],
        key=lambda e: int(e.get("cursor", 0)),
    )
    event_idx = 0
    applied_events = []

    for i in range(start, stop):
        c = candles[i]
        high = float(c["high"])
        low = float(c["low"])
        reveal.append(c)

        while event_idx < len(events) and int(events[event_idx].get("cursor", -1)) == i:
            ev = events[event_idx]
            ev_type = str(ev.get("type") or "")
            close = float(c["close"])
            if ev_type == "move_sl":
                active_sl = float(ev.get("price"))
            elif ev_type == "move_sl_be":
                active_sl = entry
            elif ev_type == "partial":
                pct = max(0.0, min(float(ev.get("fraction", 0.5)), remaining_frac))
                move = (close - entry) if direction == "long" else (entry - close)
                banked_r += pct * (move / risk)
                remaining_frac -= pct
            elif ev_type == "close":
                move = (close - entry) if direction == "long" else (entry - close)
                banked_r += remaining_frac * (move / risk)
                remaining_frac = 0.0
                outcome, exit_price, exit_time, exit_cursor = "manual_close", close, c["time"], i
                applied_events.append({**ev, "applied_price": close})
                break
            applied_events.append(ev)
            event_idx += 1
        if outcome == "manual_close":
            break

        if direction == "long":
            mfe = max(mfe, high - entry)
            mae = max(mae, entry - low)
            # Conservative same-bar ordering: if SL and TP are both inside one
            # candle, count the stop first. No intrabar path fantasy.
            if low <= active_sl:
                outcome, exit_price, exit_time, exit_cursor = "sl", active_sl, c["time"], i
                break
            if high >= tp:
                outcome, exit_price, exit_time, exit_cursor = "tp", tp, c["time"], i
                break
        else:
            mfe = max(mfe, entry - low)
            mae = max(mae, high - entry)
            if high >= active_sl:
                outcome, exit_price, exit_time, exit_cursor = "sl", active_sl, c["time"], i
                break
            if low <= tp:
                outcome, exit_price, exit_time, exit_cursor = "tp", tp, c["time"], i
                break

    r_multiple = banked_r
    if outcome == "tp":
        r_multiple += remaining_frac * (reward / risk)
    elif outcome == "sl":
        stop_r = ((active_sl - entry) / risk) if direction == "long" else ((entry - active_sl) / risk)
        r_multiple += remaining_frac * stop_r
    elif reveal:
        last = float(reveal[-1]["close"])
        move = (last - entry) if direction == "long" else (entry - last)
        r_multiple += remaining_frac * (move / risk)

    return {
        "outcome": outcome,
        "exit_price": exit_price,
        "exit_time": exit_time,
        "exit_cursor": exit_cursor,
        "bars_elapsed": (exit_cursor - cursor) if exit_cursor is not None else len(reveal),
        "r_multiple": round(r_multiple, 4),
        "rr": round(reward / risk, 4),
        "mfe_r": round(mfe / risk, 4),
        "mae_r": round(mae / risk, 4),
        "remaining_frac": round(remaining_frac, 4),
        "active_sl": round(active_sl, 6),
        "applied_events": applied_events,
        "revealed_candles": reveal,
    }


def _strict_ict_structure_overlay(df, left: int = 3, right: int = 3) -> dict:
    import pandas as pd

    from backtesting.features.ict_structure import IctStructureConfig, build_ict_structure_index

    st = build_ict_structure_index(df, IctStructureConfig(left=left, right=right))
    structure_data = {
        "source": "strict_ict",
        "left": left,
        "right": right,
        "pivots": [],
        "bos_events": [],
    }
    pivot_list = []
    for _, row in st.iterrows():
        lbl = row.get("structure_label")
        if lbl in ("HH", "HL", "LL", "LH") and pd.notna(row.get("swing_price")):
            ts_val = pd.Timestamp(row["ts"])
            pivot = {
                "time": int(ts_val.timestamp()),
                "price": float(row["swing_price"]),
                "kind": str(lbl),
                "state": str(row.get("ict_state", "")),
            }
            structure_data["pivots"].append(pivot)
            pivot_list.append((ts_val, str(lbl), float(row["swing_price"])))

    event_specs = [
        ("bullish_bos", "bos", "bullish", "bos_level"),
        ("bearish_bos", "bos", "bearish", "bos_level"),
        ("bullish_choch", "choch", "bullish", "choch_level"),
        ("bearish_choch", "choch", "bearish", "choch_level"),
    ]
    for _, row in st.iterrows():
        ts_val = pd.Timestamp(row["ts"])
        for flag_col, ev_type, direction, level_col in event_specs:
            if not bool(row.get(flag_col, False)):
                continue
            level = row.get(level_col)
            if pd.isna(level):
                continue
            level = float(level)
            level_time = None
            for p_ts, _p_kind, p_price in reversed(pivot_list):
                if p_ts >= ts_val:
                    continue
                if abs(p_price - level) <= max(abs(level) * 0.00001, 0.01):
                    level_time = int(p_ts.timestamp())
                    break
            structure_data["bos_events"].append(
                {
                    "time": int(ts_val.timestamp()),
                    "level": level,
                    "level_time": level_time,
                    "direction": direction,
                    "event_type": ev_type,
                    "state": str(row.get("ict_state", "")),
                }
            )
    return structure_data


@app.route("/api/blind/session", methods=["POST"])
def api_blind_session():
    """
    Start a server-side candle replay session.

    Unlike /api/review/run, this endpoint never returns the full candle range.
    The full data stays in _BLIND_SESSIONS and the client only receives candles
    up to the current cursor, which is the minimum needed for trustworthy
    forward-only manual labels.
    """
    import pandas as pd

    body = request.get_json(silent=True) or {}
    symbol = str(body.get("symbol", "XAUUSD")).upper()
    tf = str(body.get("tf", "5"))
    start = body.get("start")
    end = body.get("end")
    # Context is always a strict backward slice from cursor (see
    # _blind_public_state) -- it can never leak future bars, so there's no
    # hindsight-bias reason to cap it small. Raised from 500 after user
    # feedback that even 1000 bars wasn't enough to match how they read
    # charts live (full prior history, multiple timeframes).
    context_bars = max(1, min(int(body.get("context_bars", 150)), 20_000))
    warmup_bars = max(0, min(int(body.get("warmup_bars", context_bars)), 20_000))

    try:
        from backtesting.engine.data import load_data

        df = load_data(symbol, tf=tf, start=start, end=end, asset_type=_review_asset_type(symbol))
        if df.empty:
            return jsonify({"error": "No data for requested range"}), 400
        df = df.sort_values("ts").reset_index(drop=True)
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        candles = _candles_json_from_df(df)
        if not candles:
            return jsonify({"error": "No candles after loading range"}), 400

        start_cursor = min(max(warmup_bars, 0), len(candles) - 1)
        session_id = uuid.uuid4().hex
        session = {
            "session_id": session_id,
            "symbol": symbol,
            "tf": tf,
            "start": start,
            "end": end,
            "context_bars": context_bars,
            "cursor": start_cursor,
            "candles": candles,
            "indicators": _indicator_json_from_df(df),
            "decisions": [],
            "management_events": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _BLIND_SESSIONS[session_id] = session
        return jsonify(_blind_public_state(session))
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc(limit=5)}), 500


@app.route("/api/blind/step", methods=["POST"])
def api_blind_step():
    body = request.get_json(silent=True) or {}
    session_id = str(body.get("session_id", ""))
    session = _BLIND_SESSIONS.get(session_id)
    if not session:
        return jsonify({"error": "Unknown or expired blind session"}), 404
    step = int(body.get("step", 1))
    max_step = max(1, min(int(body.get("max_step", 1)), 96))
    step = max(-max_step, min(step, max_step))
    session["cursor"] = max(0, min(session["cursor"] + step, len(session["candles"]) - 1))
    return jsonify(_blind_public_state(session))


@app.route("/api/blind/decision", methods=["POST"])
def api_blind_decision():
    body = request.get_json(silent=True) or {}
    session_id = str(body.get("session_id", ""))
    session = _BLIND_SESSIONS.get(session_id)
    if not session:
        return jsonify({"error": "Unknown or expired blind session"}), 404

    cursor = int(session["cursor"])
    candle = session["candles"][cursor]
    context_bars = int(body.get("saved_context_bars", session.get("context_bars", 150)))
    lo = max(0, cursor - max(1, context_bars) + 1)
    row = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "symbol": session["symbol"],
        "tf": session["tf"],
        "cursor": cursor,
        "visible_until": candle["time"],
        "visible_until_iso": datetime.fromtimestamp(candle["time"], tz=timezone.utc).isoformat(),
        "bias": body.get("bias"),
        "action": body.get("action"),
        "direction": body.get("direction"),
        "entry": body.get("entry"),
        "sl": body.get("sl"),
        "tp": body.get("tp"),
        "confidence": body.get("confidence"),
        "notes": body.get("notes", ""),
        "tags": body.get("tags", []),
        "drawings": body.get("drawings", []),
        "management_events": body.get("management_events", session.get("management_events", [])),
        "cursor_ohlc": candle,
        "indicator_snapshot": _indicator_snapshot(session, cursor),
        "visible_candles": session["candles"][lo: cursor + 1],
        "visible_indicators": {
            name: vals[lo: cursor + 1]
            for name, vals in session.get("indicators", {}).items()
        },
        "active_indicators": body.get("active_indicators", []),
    }
    session["decisions"].append(row)
    _blind_append_decision(row)
    return jsonify({"ok": True, "decision": row, "total": len(session["decisions"])})


@app.route("/api/blind/manage", methods=["POST"])
def api_blind_manage():
    body = request.get_json(silent=True) or {}
    session_id = str(body.get("session_id", ""))
    session = _BLIND_SESSIONS.get(session_id)
    if not session:
        return jsonify({"error": "Unknown or expired blind session"}), 404
    cursor = int(session["cursor"])
    candle = session["candles"][cursor]
    event = {
        "made_at": datetime.now(timezone.utc).isoformat(),
        "type": body.get("type"),
        "cursor": cursor,
        "visible_until": candle["time"],
        "visible_until_iso": datetime.fromtimestamp(candle["time"], tz=timezone.utc).isoformat(),
        "price": body.get("price"),
        "fraction": body.get("fraction"),
        "notes": body.get("notes", ""),
    }
    if event["type"] not in ("move_sl", "move_sl_be", "partial", "close"):
        return jsonify({"error": "Unknown management event type"}), 400
    session["management_events"].append(event)
    return jsonify({"ok": True, "event": event, "total": len(session["management_events"])})


@app.route("/api/blind/simulate", methods=["POST"])
def api_blind_simulate():
    body = request.get_json(silent=True) or {}
    session_id = str(body.get("session_id", ""))
    session = _BLIND_SESSIONS.get(session_id)
    if not session:
        return jsonify({"error": "Unknown or expired blind session"}), 404
    cursor = int(body.get("cursor", session["cursor"]))
    cursor = max(0, min(cursor, len(session["candles"]) - 1))
    max_bars = max(1, min(int(body.get("max_bars", 288)), 2_000))
    plan = {
        "direction": body.get("direction"),
        "entry": body.get("entry"),
        "sl": body.get("sl"),
        "tp": body.get("tp"),
    }
    events = body.get("management_events", session.get("management_events", []))
    try:
        return jsonify(_simulate_blind_plan(
            session["candles"],
            cursor,
            plan,
            max_bars=max_bars,
            management_events=events,
        ))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/blind/analyze")
def blind_analyze_page():
    return render_template("blind_analyze.html")


@app.route("/api/blind/analyze")
def api_blind_analyze():
    try:
        max_bars = max(1, min(int(request.args.get("max_bars", 288)), 2_000))
        rows = _jsonl_rows(_blind_store_path())
        scored = [_score_blind_decision(row, max_bars=max_bars) for row in rows]
        return jsonify({"summary": _blind_analysis_summary(scored), "rows": scored})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc(limit=5)}), 500


@app.route("/callback")
def oauth_callback_page():
    """OAuth landing page for cTrader Open API demo authentication."""
    code = request.args.get("code", "")
    error = request.args.get("error") or request.args.get("errorCode") or ""
    description = request.args.get("description", "")
    if error:
        return (
            "<!doctype html><title>OAuth Error</title>"
            "<body style='font-family:system-ui;margin:40px;max-width:760px'>"
            "<h1>OAuth Error</h1>"
            f"<p><strong>{escape(error)}</strong></p>"
            f"<p>{escape(description)}</p>"
            "</body>",
            400,
        )
    if not code:
        return (
            "<!doctype html><title>OAuth Callback</title>"
            "<body style='font-family:system-ui;margin:40px;max-width:760px'>"
            "<h1>OAuth Callback</h1>"
            "<p>No authorization code was provided.</p>"
            "</body>",
            400,
        )
    return (
        "<!doctype html><title>OAuth Code Received</title>"
        "<body style='font-family:system-ui;margin:40px;max-width:760px'>"
        "<h1>Authorization Code Received</h1>"
        "<p>This short-lived code must be exchanged for an access token. "
        "Do not paste it into chats or commit it to files.</p>"
        "<label style='display:block;font-weight:600;margin-top:20px'>Code</label>"
        f"<textarea readonly style='width:100%;height:120px'>{escape(code)}</textarea>"
        "</body>"
    )


@app.route("/api/review/run", methods=["POST"])
def api_review_run():
    """Run a backtest and return all trades as JSON for the review UI."""
    import pandas as pd
    from datetime import date, timedelta
    body = request.get_json(silent=True) or {}
    symbol   = body.get("symbol", "XAUUSD")
    tf       = body.get("tf", "5")
    start    = body.get("start")
    end      = body.get("end")
    strategy = body.get("strategy", "TrFvg")
    params   = body.get("params", {})

    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backtesting.engine.data import load_data
        from backtesting.engine.runner import run as bt_run
        from backtesting.engine.costs import ForexCosts

        load_kw = {}
        if symbol in ("XAUUSD", "XAGUSD"):
            load_kw["asset_type"] = "commodity"
        if symbol in ("BTCUSD", "ETHUSD", "ADAUSDT", "XRPUSDT"):
            load_kw["asset_type"] = "crypto"

        load_start = start
        if start and strategy == "TrIct":
            load_start = (date.fromisoformat(start) - timedelta(days=7)).isoformat()

        support_tf = "240"
        data = {
            tf: load_data(symbol, tf=tf, start=load_start, end=end, **load_kw),
            support_tf: load_data(symbol, tf=support_tf, start=load_start, end=end, **load_kw),
        }
        # ICT strategy also needs 30m structure TF
        if strategy == "TrIct":
            data["30"] = load_data(symbol, tf="30", start=load_start, end=end, **load_kw)
            if start and not data[tf].empty and "ts" in data[tf].columns:
                start_ts = pd.Timestamp(start, tz="UTC")
                data[tf] = data[tf][data[tf]["ts"] >= start_ts].reset_index(drop=True)
        # lvl1/lvl2 need their HTF regime timeframe (60m by default)
        if strategy == "Lvl1Trend" and "60" not in data:
            data["60"] = load_data(symbol, tf="60", start=load_start, end=end, **load_kw)
        # OrbWideStop's validated config also needs a faster LTF trend check (30m)
        if strategy == "OrbWideStop" and "30" not in data:
            data["30"] = load_data(symbol, tf="30", start=load_start, end=end, **load_kw)
        if data[tf].empty:
            return jsonify({"error": "No data for requested range"}), 400

        if strategy == "TrFvg":
            from backtesting.strategies.tr_fvg import TrFvg
            pip_defaults = {
                "XAUUSD": 0.1, "XAGUSD": 0.001,
                "GBPJPY": 0.01, "BTCUSD": 1.0, "ETHUSD": 1.0,
            }
            pip_size = pip_defaults.get(symbol, 0.0001)
            params.setdefault("pip_size", pip_size)
            strat = TrFvg(**params)
            costs = ForexCosts(
                pip_size=pip_size,
                pip_value_per_lot=100.0 if symbol in ("XAUUSD",) else
                                  50.0  if symbol in ("XAGUSD",) else 10.0,
            )
        elif strategy == "TrIct":
            from backtesting.crypto.strategies.ict import TrIct
            risk_pct = float(params.get("risk_pct", 0.005))
            min_rr   = float(params.get("min_rr", 1.5))
            strat = TrIct(risk_pct=risk_pct, min_rr=min_rr, sessions_only=True)
            costs = ForexCosts()
        elif strategy == "Lvl1Trend":
            import numpy as np
            from backtesting.lvl1_trend.htf_ema_vwap import HtfEmaVwap
            from backtesting.engine.regime import efficiency_ratio

            class GatedHtfEmaVwap(HtfEmaVwap):
                """ER+ATR trend gate — see backtesting/lvl1_trend/, CLEAN.md."""
                def init(self, data):
                    super().init(data)
                    er = efficiency_ratio(self._close, period=10)
                    tr_ = np.maximum(self._high - self._low, np.maximum(
                        np.abs(self._high - np.roll(self._close, 1)),
                        np.abs(self._low - np.roll(self._close, 1))))
                    atr = pd.Series(tr_).rolling(14).mean().to_numpy()
                    atr_avg100 = pd.Series(atr).rolling(100).mean().to_numpy()
                    self._gate = (er > 0.3) & (atr <= 1.3 * atr_avg100)
                def next(self, bar, state):
                    i = bar.index
                    if i >= len(self._gate) or not self._gate[i]:
                        return None
                    return super().next(bar, state)

            lvl1_cost_cfg = {
                "XAUUSD": dict(pip_size=0.01, pip_value_per_lot=1.0, fixed_spread_pips=30.0),
                "XAGUSD": dict(pip_size=0.001, pip_value_per_lot=5.0, fixed_spread_pips=40.0),
                "NAS100": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=1.5),
            }
            strat = GatedHtfEmaVwap()
            costs = ForexCosts(seed=0, **lvl1_cost_cfg.get(symbol, dict(pip_size=0.0001)))
        elif strategy == "OrbWideStop":
            from backtesting.lvl2_orb.orb_wide_stop import OrbNyWideStop
            lvl2_cost_cfg = {
                "XAUUSD": dict(pip_size=0.01, pip_value_per_lot=1.0, fixed_spread_pips=30.0),
                "XAGUSD": dict(pip_size=0.001, pip_value_per_lot=5.0, fixed_spread_pips=40.0),
                "NAS100": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=1.5),
                "US30": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=3.0),
                "SPX500": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=0.7),
            }
            strat = OrbNyWideStop(htf_key="240", ltf_key="30", multi_target=True)
            costs = ForexCosts(seed=42, **lvl2_cost_cfg.get(symbol, dict(pip_size=0.0001, pip_value_per_lot=10.0, fixed_spread_pips=1.5)))
        elif strategy == "IntradayMomentum":
            from backtesting.lvl2_intraday_momentum.intraday_momentum import IntradayMomentum
            lvl2_cost_cfg = {
                "XAUUSD": dict(pip_size=0.01, pip_value_per_lot=1.0, fixed_spread_pips=30.0),
                "XAGUSD": dict(pip_size=0.001, pip_value_per_lot=5.0, fixed_spread_pips=40.0),
                "NAS100": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=1.5),
                "US30": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=3.0),
                "SPX500": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=0.7),
            }
            strat = IntradayMomentum(stop_mode="structure")
            costs = ForexCosts(seed=42, **lvl2_cost_cfg.get(symbol, dict(pip_size=0.0001, pip_value_per_lot=10.0, fixed_spread_pips=1.5)))
        elif strategy == "OvernightDrift":
            from backtesting.lvl2_overnight_drift.overnight_drift import OvernightDrift
            lvl2_cost_cfg = {
                "XAUUSD": dict(pip_size=0.01, pip_value_per_lot=1.0, fixed_spread_pips=30.0),
                "XAGUSD": dict(pip_size=0.001, pip_value_per_lot=5.0, fixed_spread_pips=40.0),
                "NAS100": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=1.5),
                "US30": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=3.0),
                "SPX500": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=0.7),
            }
            strat = OvernightDrift(htf_key="240", stop_mode="structure")
            costs = ForexCosts(seed=42, **lvl2_cost_cfg.get(symbol, dict(pip_size=0.0001, pip_value_per_lot=10.0, fixed_spread_pips=1.5)))
        else:
            return jsonify({"error": f"Unknown strategy: {strategy}"}), 400

        result = bt_run(strat, data, entry_tf=tf, costs=costs, initial_equity=10_000)
        df_trades = result.to_df()

        trades_json = []
        for _, row in df_trades.iterrows():
            sl_val = float(row["sl"]) if pd.notna(row["sl"]) else None
            tp1_val = float(row["tp1"]) if pd.notna(row["tp1"]) else None
            entry_val = float(row["entry_price"])
            # Planned R:R at entry (target distance / stop distance) -- distinct
            # from the realized r_multiple, which reflects what actually
            # happened (partial fills, breakeven stops, trailing, etc).
            planned_rr = None
            if sl_val is not None and tp1_val is not None:
                stop_dist = abs(entry_val - sl_val)
                if stop_dist > 0:
                    planned_rr = round(abs(tp1_val - entry_val) / stop_dist, 2)
            return_pct = round(float(row["pnl"]) / 10_000 * 100, 3)  # vs the $10k backtest baseline
            trades_json.append({
                "id": int(row["id"]) if pd.notna(row["id"]) else 0,
                "direction": str(row["direction"]),
                "entry_time": row["entry_time"].isoformat() if hasattr(row["entry_time"], "isoformat") else str(row["entry_time"]),
                "exit_time":  row["exit_time"].isoformat()  if hasattr(row["exit_time"],  "isoformat") else str(row["exit_time"]),
                "duration_min": float(row["duration_min"]),
                "entry_price": entry_val,
                "exit_price":  float(row["exit_price"]),
                "exit_reason": str(row["exit_reason"]),
                "planned_rr": planned_rr,
                "return_pct": return_pct,
                "sl": sl_val,
                "tp1": float(row["tp1"]) if pd.notna(row["tp1"]) else None,
                "pnl": float(row["pnl"]),
                "r_multiple": float(row["r_multiple"]) if pd.notna(row["r_multiple"]) else None,
                "label": str(row["label"]) if row["label"] else "",
            })

        df5 = data[tf].copy()
        candles_json = _candles_json_from_df(df5)

        # Strict ICT structure overlay: HH/HL -> CHoCH -> LL/LH -> BOS, and mirror.
        structure_data = {"pivots": [], "bos_events": []}
        try:
            from backtesting.structure_lib.fvg import detect_fvgs
            from backtesting.structure_lib.ob import detect_order_blocks

            df_src = df5.copy().set_index("ts").sort_index()
            df_overlay = df5[["ts", "open", "high", "low", "close"]].copy()
            structure_data = _strict_ict_structure_overlay(df_overlay, left=3, right=3)

            # 30m for OBs only
            df30 = df_src.resample("30min").agg(
                {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
            ).dropna(subset=["open"])

            if len(df30) > 10:
                from backtesting.structure_lib.swing import swing_points
                from backtesting.structure_lib.labels import label_structure
                swings, levels = swing_points(df30, swing_length=1, causal=True)
                labels_df = label_structure(df30, swings, levels)

                # Per-trade OBs via structure_lib
                obs = detect_order_blocks(df30, labels_df, lookback=5, min_body_pct=0.3)

                def _ts(s):
                    """Timezone-safe pd.Timestamp — always UTC."""
                    t = pd.Timestamp(s)
                    return t if t.tz is not None else t.tz_localize("UTC")

                for trade in trades_json:
                    try:
                        entry_ts_val = _ts(trade["entry_time"])
                        idx30 = df30.index.searchsorted(entry_ts_val, side="right") - 1
                        if idx30 < 3:
                            continue
                        direction = trade["direction"]
                        entry_price = float(trade["entry_price"])
                        for ob in reversed(obs):
                            if ob.time > df30.index[idx30]:
                                continue
                            if direction == "LONG" and ob.kind == "bullish" and ob.bottom < entry_price:
                                ob_end = ob.time + pd.Timedelta("30min")
                                trade["demand_ob"] = {
                                    "time_start": int(ob.time.timestamp()),
                                    "time_end":   int(ob_end.timestamp()),
                                    "high": float(ob.top), "low": float(ob.bottom),
                                }
                                break
                            elif direction == "SHORT" and ob.kind == "bearish" and ob.top > entry_price:
                                ob_end = ob.time + pd.Timedelta("30min")
                                trade["supply_ob"] = {
                                    "time_start": int(ob.time.timestamp()),
                                    "time_end":   int(ob_end.timestamp()),
                                    "high": float(ob.top), "low": float(ob.bottom),
                                }
                                break
                    except Exception:
                        pass

                # Per-trade unmitigated FVGs (5m) — CE-based mitigation (gap touch ≠ mitigated)
                fvgs_5m = detect_fvgs(df_src)

                for trade in trades_json:
                    try:
                        entry_ts_val = _ts(trade["entry_time"])
                        entry_i = df_src.index.searchsorted(entry_ts_val, side="right")
                        ctx_start = max(0, entry_i - 150)
                        trade_fvgs = []
                        for fvg in fvgs_5m:
                            if fvg.c3_idx >= entry_i or fvg.c1_idx < ctx_start:
                                continue
                            ce = (fvg.top + fvg.bottom) / 2
                            mitigated = False
                            for k in range(fvg.c3_idx + 1, entry_i):
                                c = df_src.iloc[k]
                                # Mitigated only when price crosses CE, not just touches the gap edge
                                if fvg.kind == "bearish" and c["high"] >= ce:
                                    mitigated = True; break
                                elif fvg.kind == "bullish" and c["low"] <= ce:
                                    mitigated = True; break
                            if not mitigated:
                                trade_fvgs.append({
                                    "kind":    fvg.kind,
                                    "top":     float(fvg.top),
                                    "bottom":  float(fvg.bottom),
                                    "c1_time": int(df_src.index[fvg.c1_idx].timestamp()),
                                    "c3_time": int(df_src.index[fvg.c3_idx].timestamp()),
                                })
                        trade["fvgs"] = trade_fvgs
                    except Exception:
                        pass

        except Exception:
            pass  # structure overlay is non-critical

        report = result.report
        # strip non-serialisable fields (equity_curve list of np.float64 is fine, but drop large arrays)
        safe_report = {k: v for k, v in report.items()
                       if k not in ("equity_curve", "trade_pnls", "trade_r_multiples")}
        safe_report["trades"] = int(safe_report.get("trades", 0))

        # Blind review mode: strip every outcome field so the reviewer only sees
        # what was knowable at signal time (entry/sl/tp1), never the result.
        # Aggregate stats are hidden too — seeing WR/PF upfront biases labels
        # toward matching the displayed number. This is the fix for the
        # hindsight-bias finding in selection_edge_unmeasurable (211 reviews,
        # 73% next-bar-favorable) — see CLEAN.md §11.
        blind = bool(body.get("blind", False))
        if blind:
            OUTCOME_FIELDS = ("exit_time", "exit_price", "exit_reason", "pnl", "r_multiple")
            for t in trades_json:
                for f in OUTCOME_FIELDS:
                    t.pop(f, None)
            safe_report = {"trades": safe_report.get("trades", 0)}

        return jsonify({
            "symbol": symbol,
            "tf": tf,
            "params": params,
            "report": safe_report,
            "trades": trades_json,
            "candles": candles_json,
            "structure": structure_data,
            "blind": blind,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc(limit=5)}), 500


@app.route("/api/review/ict-events", methods=["POST"])
def api_review_ict_events():
    """Load strict ICT direction events as reviewable pseudo-trades."""
    import pandas as pd

    body = request.get_json(silent=True) or {}
    symbol = str(body.get("symbol", "XAUUSD")).upper()
    tf = str(body.get("tf", "5"))
    predictor = str(body.get("predictor", "bearish_bos"))
    session = str(body.get("session", "asia"))
    direction = str(body.get("direction", "short"))
    target = str(body.get("target", "1.5r"))
    limit = int(body.get("limit", 50))

    default_sample = Path(__file__).resolve().parent.parent / "backtesting" / "results" / "ict_review_samples_XAUUSD_bearish_bos_asia_1.5r.csv"
    default_events = Path(__file__).resolve().parent.parent / "backtesting" / "results" / "ict_direction_rolling_180d_l3r3_events.csv"
    events_path = Path(body.get("events_path") or (default_sample if default_sample.exists() else default_events))
    if not events_path.is_absolute():
        events_path = Path(__file__).resolve().parent.parent / events_path
    if not events_path.exists():
        return jsonify({"error": f"Missing events file: {events_path}"}), 404

    try:
        from backtesting.engine.data import load_data

        events = pd.read_csv(events_path)
        if events.empty:
            return jsonify({"error": "Events file is empty"}), 400
        events["ts"] = pd.to_datetime(events["ts"], utc=True)
        filtered = events[
            (events["symbol"].astype(str).str.upper() == symbol)
            & (events["predictor"].astype(str) == predictor)
            & (events["session"].astype(str) == session)
            & (events["direction"].astype(str) == direction)
        ].copy()
        if filtered.empty:
            # A pre-filtered sample can omit one of these columns in future; fall back to symbol-only.
            filtered = events[events["symbol"].astype(str).str.upper() == symbol].copy()
        if filtered.empty:
            return jsonify({"error": f"No matching events in {events_path.name}"}), 404

        outcome_col = f"outcome_{target}"
        hit_col = f"hit_{target}"
        if outcome_col not in filtered.columns:
            return jsonify({"error": f"Missing outcome column: {outcome_col}"}), 400

        if "review_bucket" in filtered.columns:
            order = {"best": 0, "worst": 1}
            filtered["_bucket_order"] = filtered["review_bucket"].map(order).fillna(2)
            filtered = filtered.sort_values(["_bucket_order", "ts"])
        else:
            filtered = filtered.reindex(filtered[outcome_col].abs().sort_values(ascending=False).index)
        filtered = filtered.head(limit).reset_index(drop=True)

        start_ts = filtered["ts"].min() - pd.Timedelta(days=3)
        end_ts = filtered["ts"].max() + pd.Timedelta(days=3)
        df = load_data(
            symbol,
            tf=tf,
            start=start_ts.isoformat(),
            end=end_ts.isoformat(),
            asset_type=_review_asset_type(symbol),
        )
        if df.empty:
            return jsonify({"error": f"No candle data for {symbol} {tf}"}), 404
        df = df.sort_values("ts").reset_index(drop=True)
        df["ts"] = pd.to_datetime(df["ts"], utc=True)

        target_r = float(target.replace("r", ""))
        trades_json = []
        for idx, row in filtered.iterrows():
            event_ts = pd.Timestamp(row["ts"])
            candle_i = int((df["ts"] - event_ts).abs().idxmin())
            candle = df.iloc[candle_i]
            entry = float(candle["close"])
            risk = float(row.get("risk_price") or 0.0)
            if risk <= 0:
                continue
            is_long = str(row.get("direction", direction)).lower() == "long"
            sl = entry - risk if is_long else entry + risk
            tp = entry + target_r * risk if is_long else entry - target_r * risk
            exit_ts = event_ts + pd.Timedelta(minutes=int(tf) * 24 if tf.isdigit() else 120)
            outcome = float(row.get(outcome_col, 0.0))
            hit = bool(row.get(hit_col, False))
            label_bits = [str(row.get("predictor", predictor)), str(row.get("session", session))]
            if "review_bucket" in row and pd.notna(row.get("review_bucket")):
                label_bits.insert(0, str(row.get("review_bucket")))
            trades_json.append(
                {
                    "id": idx + 1,
                    "direction": "LONG" if is_long else "SHORT",
                    "entry_time": event_ts.isoformat(),
                    "exit_time": exit_ts.isoformat(),
                    "duration_min": float((exit_ts - event_ts).total_seconds() / 60),
                    "entry_price": entry,
                    "exit_price": tp if hit else sl if outcome <= -1 else entry + (outcome * risk if is_long else -outcome * risk),
                    "exit_reason": f"ICT_{target.upper()}_{'HIT' if hit else 'MISS'}",
                    "sl": sl,
                    "tp1": tp,
                    "pnl": outcome,
                    "r_multiple": outcome,
                    "label": " | ".join(label_bits),
                    "mfe_r": float(row.get("mfe_r", 0.0)),
                    "mae_r": float(row.get("mae_r", 0.0)),
                }
            )

        candles_json = _candles_json_from_df(df)
        structure_data = _strict_ict_structure_overlay(df[["ts", "open", "high", "low", "close"]], left=3, right=3)
        report = {
            "trades": len(trades_json),
            "win_rate": sum(1 for t in trades_json if t["r_multiple"] > 0) / max(len(trades_json), 1),
            "profit_factor": 0,
            "max_drawdown_pct": 0,
        }
        gains = sum(t["r_multiple"] for t in trades_json if t["r_multiple"] > 0)
        losses = abs(sum(t["r_multiple"] for t in trades_json if t["r_multiple"] < 0))
        report["profit_factor"] = gains / losses if losses > 0 else gains
        return jsonify(
            {
                "symbol": symbol,
                "tf": tf,
                "params": {
                    "source": "strict_ict_events",
                    "events_path": str(events_path),
                    "predictor": predictor,
                    "session": session,
                    "direction": direction,
                    "target": target,
                },
                "report": report,
                "trades": trades_json,
                "candles": candles_json,
                "structure": structure_data,
            }
        )

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc(limit=5)}), 500


@app.route("/api/review/candles")
def api_review_candles():
    """Return OHLCV candles around a trade for the review chart."""
    import pandas as pd
    symbol = request.args.get("symbol", "XAUUSD")
    tf     = request.args.get("tf", "5")
    center = request.args.get("center")   # ISO timestamp of trade entry
    before = int(request.args.get("before", 200))   # bars before entry
    after  = int(request.args.get("after",  100))   # bars after entry

    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backtesting.engine.data import load_data

        load_kw = {}
        if symbol in ("BTCUSD", "ETHUSD", "ADAUSDT", "XRPUSDT"):
            load_kw["asset_type"] = "crypto"

        # Load a wide window, then slice around center
        _ts = pd.Timestamp(center) if center else None
        center_ts = (_ts.tz_convert("UTC") if _ts is not None and _ts.tzinfo else
                     _ts.tz_localize("UTC") if _ts is not None else None)
        if center_ts:
            tf_min = {"1": 1, "5": 5, "15": 15, "60": 60, "240": 240}.get(tf, 5)
            pad_before = timedelta(minutes=before * tf_min * 1.5)
            pad_after  = timedelta(minutes=after  * tf_min * 1.5)
            start = (center_ts - pad_before).isoformat()
            end   = (center_ts + pad_after).isoformat()
        else:
            start = end = None

        df = load_data(symbol, tf=tf, start=start, end=end, **load_kw)
        if df.empty:
            return jsonify([])

        # Find center index
        if center_ts is not None:
            idx = (df["ts"] - center_ts).abs().idxmin()
            lo = max(0, idx - before)
            hi = min(len(df), idx + after + 1)
            df = df.iloc[lo:hi]

        candles = [
            {
                "time": int(row["ts"].timestamp()),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low":  float(row["low"]),
                "close": float(row["close"]),
            }
            for _, row in df.iterrows()
        ]
        return jsonify(candles)

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc(limit=5)}), 500


@app.route("/api/review/label", methods=["POST"])
def api_review_label():
    """Persist a user label on a trade (stored in a local JSON file)."""
    import json as json_mod
    body = request.get_json(silent=True) or {}
    store_path = Path(__file__).resolve().parent / "review_labels.json"
    labels: dict = {}
    if store_path.exists():
        with open(store_path) as f:
            labels = json_mod.load(f)

    strategy = body.get("strategy", "?")
    key = f"{strategy}_{body.get('symbol','?')}_{body.get('tf','?')}_{body.get('entry_time','?')}"
    labels[key] = {
        "strategy": strategy,
        "symbol": body.get("symbol"),
        "tf": body.get("tf"),
        "entry_time": body.get("entry_time"),
        "label": body.get("label"),       # "good" / "bad" / "skip"
        "notes": body.get("notes", ""),
        "params": body.get("params", {}),
        "drawings": body.get("drawings", []),
        "markers": body.get("markers", []),
    }
    with open(store_path, "w") as f:
        json_mod.dump(labels, f, indent=2)
    return jsonify({"ok": True, "total": len(labels)})


if __name__ == "__main__":
    journal_db.init_db()
    port = int(os.getenv("WEBAPP_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
