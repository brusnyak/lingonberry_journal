import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask import Flask, abort, jsonify, render_template, request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import journal_db
from core.exporter import export_ml_dataset
from infra.market_data import get_timeframe_for_asset, load_ohlcv_with_cache, replay_window
from infra.pine_bridge import process_pine_payload
from jobs.sltp_poller import SLTPPoller

app = Flask(__name__, template_folder="templates", static_folder="static")


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
    stats = journal_db.get_stats(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    trades = journal_db.get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
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
        session = t.get("session") or "unknown"
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
    
    return {
        "stats": stats,
        "equity": equity,
        "open_trades": open_trades,
        "trades": sorted(trades, key=lambda x: x["ts_open"], reverse=True),
        "calendar": calendar,
        "analytics": direction_stats,
        "monte_carlo": journal_db.get_monte_carlo_stats(account_id=account_id, from_ts=from_ts, to_ts=to_ts),
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


@app.route("/weekly")
def weekly_page():
    journal_db.init_db()
    accounts = journal_db.get_accounts()
    account_id = _parse_account_id(request.args.get("account_id")) or (accounts[0]["id"] if accounts else 1)
    week_start = request.args.get("week_start") or _default_week_start_iso()
    review = journal_db.get_weekly_review(account_id=account_id, week_start=week_start)
    trades = journal_db.get_all_trades(account_id=account_id)

    week_dt = datetime.fromisoformat(week_start)
    week_end = (week_dt + timedelta(days=7)).date().isoformat()
    week_trades = [t for t in trades if week_start <= t["ts_open"][:10] < week_end]

    stats = journal_db.get_stats(account_id=account_id, from_ts=week_start, to_ts=f"{week_end}T23:59:59+00:00")

    return render_template(
        "weekly.html",
        accounts=accounts,
        selected_account_id=account_id,
        week_start=week_start,
        stats=stats,
        week_trades_json=json.dumps(week_trades),
        review_json=json.dumps(review),
        now=datetime.now().strftime("%d %b %Y"),
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
        timezone_name=body.get("timezone", "UTC"),
    )
    return jsonify({"account_id": account_id, "account": journal_db.get_account(account_id)}), 201


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
    return jsonify(journal_db.get_all_trades(account_id=account_id))


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


@app.route("/api/analytics/monte-carlo")
def api_monte_carlo():
    account_id = _parse_account_id(request.args.get("account_id"))
    result = journal_db.get_monte_carlo_stats(
        account_id=account_id,
        from_ts=request.args.get("from"),
        to_ts=request.args.get("to"),
    )
    return jsonify(result)


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
