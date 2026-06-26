import json
import os
import sys
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


@app.route("/api/review/run", methods=["POST"])
def api_review_run():
    """Run a backtest and return all trades as JSON for the review UI."""
    import pandas as pd
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
        if symbol in ("BTCUSD", "ETHUSD", "ADAUSDT", "XRPUSDT"):
            load_kw["asset_type"] = "crypto"

        support_tf = "240"
        data = {
            tf: load_data(symbol, tf=tf, start=start, end=end, **load_kw),
            support_tf: load_data(symbol, tf=support_tf, start=start, end=end, **load_kw),
        }
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
        else:
            return jsonify({"error": f"Unknown strategy: {strategy}"}), 400

        result = bt_run(strat, data, entry_tf=tf, costs=costs, initial_equity=10_000)
        df_trades = result.to_df()

        trades_json = []
        for _, row in df_trades.iterrows():
            trades_json.append({
                "id": int(row["id"]) if pd.notna(row["id"]) else 0,
                "direction": str(row["direction"]),
                "entry_time": row["entry_time"].isoformat() if hasattr(row["entry_time"], "isoformat") else str(row["entry_time"]),
                "exit_time":  row["exit_time"].isoformat()  if hasattr(row["exit_time"],  "isoformat") else str(row["exit_time"]),
                "duration_min": float(row["duration_min"]),
                "entry_price": float(row["entry_price"]),
                "exit_price":  float(row["exit_price"]),
                "exit_reason": str(row["exit_reason"]),
                "sl": float(row["sl"]) if pd.notna(row["sl"]) else None,
                "tp1": float(row["tp1"]) if pd.notna(row["tp1"]) else None,
                "pnl": float(row["pnl"]),
                "r_multiple": float(row["r_multiple"]) if pd.notna(row["r_multiple"]) else None,
                "label": str(row["label"]) if row["label"] else "",
            })

        # Embed full candle array so the frontend never needs a second request
        import numpy as np
        df5 = data[tf].copy()
        candles_json = [
            {
                "time": int(row["ts"].timestamp()),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low":  float(row["low"]),
                "close": float(row["close"]),
            }
            for _, row in df5.iterrows()
        ]

        # Structure overlay — 30m structure via structure_lib (proper BOS/ChoCH, FVGs, OBs)
        structure_data = {"pivots": [], "bos_events": []}
        try:
            from backtesting.structure_lib.swing import swing_points
            from backtesting.structure_lib.labels import label_structure
            from backtesting.structure_lib.fvg import detect_fvgs
            from backtesting.structure_lib.ob import detect_order_blocks

            df_src = df5.copy().set_index("ts").sort_index()

            # 30m for structure
            df30 = df_src.resample("30min").agg(
                {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
            ).dropna(subset=["open"])

            if len(df30) > 10:
                swings, levels = swing_points(df30, swing_length=1, causal=True)
                labels_df = label_structure(df30, swings, levels)

                # Build pivot list with timestamps for BOS line start anchoring
                pivot_list = []  # (ts, kind, price)
                for ts_idx in df30.index:
                    lbl = labels_df.loc[ts_idx, "structure_label"] if ts_idx in labels_df.index else None
                    if lbl in ("HH", "HL", "LL", "LH"):
                        level_val = levels.loc[ts_idx] if ts_idx in levels.index else float("nan")
                        if not pd.isna(level_val):
                            structure_data["pivots"].append({
                                "time":  int(ts_idx.timestamp()),
                                "price": float(level_val),
                                "kind":  lbl,
                            })
                            pivot_list.append((ts_idx, lbl, float(level_val)))

                # BOS/ChoCH events — find level_time by matching broken level to pivot history
                for ts_idx in labels_df.index:
                    row = labels_df.loc[ts_idx]
                    for ev_type, direction, level_col in [
                        ("bos",   "bullish", "bos_level"),
                        ("bos",   "bearish", "bos_level"),
                        ("choch", "bullish", "choch_level"),
                        ("choch", "bearish", "choch_level"),
                    ]:
                        flag_col = f"{direction}_{ev_type}"
                        if not (flag_col in row and row[flag_col]):
                            continue
                        lv = row.get(level_col, float("nan"))
                        if pd.isna(lv):
                            continue
                        # Find the most recent pivot before this bar that matches the broken level
                        level_time = None
                        for p_ts, p_kind, p_price in reversed(pivot_list):
                            if p_ts >= ts_idx:
                                continue
                            if abs(p_price - float(lv)) < 0.01:
                                level_time = int(p_ts.timestamp())
                                break
                        structure_data["bos_events"].append({
                            "time":       int(ts_idx.timestamp()),
                            "level":      float(lv),
                            "level_time": level_time,
                            "direction":  direction,
                            "event_type": ev_type,
                        })

                # Per-trade OBs via structure_lib (tied to BOS/ChoCH)
                obs = detect_order_blocks(df30, labels_df, lookback=5, min_body_pct=0.3)
                ts30_arr = df30.index.to_numpy()

                for trade in trades_json:
                    try:
                        entry_ts_val = pd.Timestamp(trade["entry_time"])
                        idx30 = int(np.searchsorted(ts30_arr, np.datetime64(entry_ts_val), side="right")) - 1
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

                # Per-trade unmitigated FVGs (5m)
                fvgs_5m = detect_fvgs(df_src)
                df5_idx = df_src.index.to_numpy()

                for trade in trades_json:
                    try:
                        entry_ts_val = pd.Timestamp(trade["entry_time"])
                        entry_i = int(np.searchsorted(df5_idx, np.datetime64(entry_ts_val), side="right"))
                        ctx_start = max(0, entry_i - 150)
                        trade_fvgs = []
                        for fvg in fvgs_5m:
                            if fvg.c3_idx >= entry_i or fvg.c1_idx < ctx_start:
                                continue
                            # Check mitigation between c3 and entry
                            mitigated = False
                            for k in range(fvg.c3_idx + 1, entry_i):
                                c = df_src.iloc[k]
                                if fvg.kind == "bearish" and c["high"] >= fvg.bottom:
                                    mitigated = True; break
                                elif fvg.kind == "bullish" and c["low"] <= fvg.top:
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

        return jsonify({
            "symbol": symbol,
            "tf": tf,
            "params": params,
            "report": safe_report,
            "trades": trades_json,
            "candles": candles_json,
            "structure": structure_data,
        })

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

    key = f"{body.get('symbol','?')}_{body.get('tf','?')}_{body.get('entry_time','?')}"
    labels[key] = {
        "symbol": body.get("symbol"),
        "tf": body.get("tf"),
        "entry_time": body.get("entry_time"),
        "label": body.get("label"),       # "good" / "bad" / "skip"
        "notes": body.get("notes", ""),
        "params": body.get("params", {}),
    }
    with open(store_path, "w") as f:
        json_mod.dump(labels, f, indent=2)
    return jsonify({"ok": True, "total": len(labels)})


if __name__ == "__main__":
    journal_db.init_db()
    port = int(os.getenv("WEBAPP_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
