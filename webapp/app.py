import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import journal_db, chart_generator
from core.exporter import export_ml_dataset
from core.raw_trade_import import parse_raw_trades
from infra.market_data import get_timeframe_for_asset, load_ohlcv_with_cache, replay_window
from infra.pine_bridge import process_pine_payload
from jobs.sltp_poller import SLTPPoller

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
            from datetime import datetime, timedelta
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
                
                # Update trade with chart path
                journal_db.update_trade_chart_path(trade_id, filename)
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

        account_id = _parse_account_id(request.args.get("account_id"))
        if not account_id:
            account_id = int(body.get("account_id", 1))

        account = journal_db.get_account(account_id)
        if not account:
            return jsonify({"error": "Account not found", "account_id": account_id}), 404

        tz_offset = int(body.get("timezone_offset_hours", 2))
        timeframe = body.get("timeframe", "M30")

        trades = parse_raw_trades(raw_text, tz_offset_hours=tz_offset)
        if not trades:
            return jsonify({"error": "No trades parsed from input"}), 400

        imported = []
        skipped = 0
        for t in trades:
            try:
                trade_id = journal_db.create_trade(
                    account_id=account_id,
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
                    "symbol": t["symbol"],
                    "ts_open": t["ts_open"],
                })
            except Exception:
                skipped += 1

        return jsonify({
            "imported": imported,
            "imported_count": len(imported),
            "skipped": skipped,
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


@app.route("/api/jobs/sltp-check", methods=["POST"])
def api_sltp_check():
    body = request.get_json(force=True, silent=True) or {}
    account_id = body.get("account_id")
    poller = SLTPPoller()
    result = poller.run_once(account_id=int(account_id) if account_id is not None else None)
    return jsonify({"closed": result, "count": len(result)})


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
    
    from infra.ctrader_ingest import get_trade_replay_data
    candles = get_trade_replay_data(
        symbol=trade["symbol"],
        timeframe=trade.get("timeframe", "H1"),
        from_ts=trade["ts_open"],
        to_ts=trade.get("ts_close") or datetime.now(timezone.utc).isoformat()
    )
    return jsonify({"trade": trade, "candles": candles})


if __name__ == "__main__":
    journal_db.init_db()
    port = int(os.getenv("WEBAPP_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
