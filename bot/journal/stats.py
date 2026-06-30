"""
Trade statistics and analytics.

Depends on crud.py for data access and schema.py for helpers.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bot.journal.crud import (
    get_account,
    get_accounts,
    get_all_trades,
    get_trade,
)
from bot.journal.schema import (
    _parse_timestamp,
    _safe_float,
    get_connection,
)


# ── Statistics ───────────────────────────────────────────────────────────────


def get_stats(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    account = get_account(account_id) if account_id else (get_accounts()[0] if get_accounts() else None)
    initial_balance = float(account["initial_balance"]) if account else 0.0

    trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    closed_trades = [t for t in trades if t["outcome"] != "OPEN"]

    if not closed_trades:
        return {
            "total_trades": 0, "win_rate": 0, "total_pnl_usd": 0,
            "avg_win_usd": 0, "avg_loss_usd": 0, "profit_factor": 0,
            "max_drawdown_pct": 0, "sharpe_ratio": 0, "avg_rr": 0,
            "initial_balance": initial_balance, "balance": initial_balance,
            "growth_pct": 0, "wins": 0, "losses": 0, "expectancy": 0, "daily_pnl": 0,
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
    total_wins = sum(t["pnl_usd"] for t in wins if t.get("pnl_usd") is not None)
    total_losses = abs(sum(t["pnl_usd"] for t in losses if t.get("pnl_usd") is not None))

    win_rate = (len(wins) / len(closed_trades)) * 100 if closed_trades else 0
    avg_win = total_wins / len(wins) if wins else 0
    avg_loss = total_losses / len(losses) if losses else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else (float('inf') if total_wins > 0 else 0)

    equity = initial_balance
    peak = initial_balance
    max_dd = 0
    for t in sorted(closed_trades, key=lambda x: x.get("ts_close", "")):
        equity += float(t.get("pnl_usd", 0) or 0)
        peak = max(peak, equity)
        dd = ((peak - equity) / peak * 100) if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    returns = [float(t.get("pnl_pct") or 0.0) / 100.0 for t in closed_trades]
    sharpe_ratio = 0.0
    if len(returns) > 1:
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)
        if std_dev > 0:
            sharpe_ratio = (mean_ret / std_dev) * math.sqrt(len(returns))

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


# ── Analytics ────────────────────────────────────────────────────────────────


def get_analytics_breakdown(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    closed_trades = [t for t in trades if t["outcome"] != "OPEN"]

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
        for t in trades_seq:
            pnl = _safe_float(t.get("pnl_usd"), 0.0)
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

    long_trades = [t for t in closed_trades if str(t.get("direction", "")).upper() == "LONG"]
    short_trades = [t for t in closed_trades if str(t.get("direction", "")).upper() == "SHORT"]

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


# ── Week stats & direction correctness ───────────────────────────────────────


def get_week_stats(
    week_start: str,
    account_id: Optional[int] = None,
    is_perfect: Optional[bool] = None,
) -> Dict[str, Any]:
    from bot.journal.crud import get_trades_by_week

    trades = get_trades_by_week(week_start, account_id, is_perfect)

    if not trades:
        return {
            "week_start": week_start, "total_trades": 0, "wins": 0,
            "losses": 0, "win_rate": 0, "net_pnl": 0, "avg_win": 0,
            "avg_loss": 0, "profit_factor": 0, "best_trade": 0,
            "worst_trade": 0, "avg_rr": 0,
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


def analyze_direction_correctness(
    trade_id: Optional[int] = None,
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    import pandas as pd
    from infra.market_data import load_ohlcv_with_cache

    if trade_id:
        trades = [get_trade(trade_id)]
        if not trades[0]:
            return {"error": f"Trade {trade_id} not found"}
    else:
        trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
        trades = [t for t in trades if t["outcome"] not in ["OPEN"]]

    results = []
    updated_count = 0

    for trade in trades:
        try:
            if not trade.get("ts_close"):
                results.append({"trade_id": trade["id"], "direction_correct": None, "analysis": "No close timestamp"})
                continue

            timeframe = trade.get("timeframe") or "m15"
            ts_close = datetime.fromisoformat(trade["ts_close"].replace("Z", "+00:00"))
            end_time = ts_close + timedelta(hours=24)

            df = load_ohlcv_with_cache(
                symbol=trade["symbol"], asset_type=trade.get("asset_type") or "forex",
                timeframe=timeframe, start=ts_close, end=end_time, ttl_seconds=3600,
            )

            if df.empty:
                results.append({"trade_id": trade["id"], "direction_correct": None, "analysis": "No market data available"})
                continue

            direction = str(trade.get("direction", "")).upper()

            if trade.get("pnl_usd", 0) > 0 or trade.get("outcome") == "TP":
                direction_correct = 1
                analysis = "Win: Direction confirmed by profit"
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE trades SET direction_correct = ? WHERE id = ?", (1, trade["id"]))
                conn.commit()
                conn.close()
                updated_count += 1
                results.append({"trade_id": trade["id"], "direction_correct": True, "analysis": analysis})
                continue

            if not trade.get("sl_price") or not trade.get("tp_price"):
                results.append({"trade_id": trade["id"], "direction_correct": 0, "analysis": "Loss: No SL/TP defined for stop-out check"})
                continue

            if not direction or direction not in ["LONG", "SHORT"]:
                results.append({"trade_id": trade["id"], "direction_correct": 0, "analysis": f"Invalid direction: {trade.get('direction')}"})
                continue

            sl_price = float(trade["sl_price"])
            tp_price = float(trade["tp_price"])

            if direction == "LONG":
                max_price = df["high"].max()
                direction_correct = max_price >= tp_price
                analysis = f"Max price after SL: {max_price:.5f}, TP: {tp_price:.5f}"
            else:
                min_price = df["low"].min()
                direction_correct = min_price <= tp_price
                analysis = f"Min price after SL: {min_price:.5f}, TP: {tp_price:.5f}"

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE trades SET direction_correct = ? WHERE id = ?",
                (1 if direction_correct else 0, trade["id"]),
            )
            conn.commit()
            conn.close()
            updated_count += 1

            results.append({"trade_id": trade["id"], "direction_correct": direction_correct, "analysis": analysis})

        except Exception as e:
            import traceback
            results.append({
                "trade_id": trade["id"],
                "direction_correct": None,
                "analysis": f"Error: {str(e)}\n{traceback.format_exc()}",
            })

    if trade_id:
        return results[0] if results else {"error": "No analysis performed"}
    return {"analyzed": len(results), "updated": updated_count, "results": results}


def get_direction_accuracy_stats(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, Any]:
    trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    closed_trades = [t for t in trades if t["outcome"] != "OPEN"]

    analyzed_trades = [t for t in closed_trades if t.get("direction_correct") is not None]

    if not analyzed_trades:
        analyze_direction_correctness(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
        trades = get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
        closed_trades = [t for t in trades if t["outcome"] != "OPEN"]
        analyzed_trades = [t for t in closed_trades if t.get("direction_correct") is not None]

    if not analyzed_trades:
        return {
            "overall_accuracy": 0, "win_accuracy": 0, "loss_accuracy": 0,
            "total_analyzed": 0, "correct_direction": 0,
            "by_direction": {"long": {"total": 0, "correct": 0, "accuracy": 0},
                             "short": {"total": 0, "correct": 0, "accuracy": 0}},
            "note": "No trades analyzed. Try logging some wins or running analysis.",
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
            "long": {"total": len(long_trades), "correct": len(long_correct),
                     "accuracy": (len(long_correct) / len(long_trades) * 100) if long_trades else 0},
            "short": {"total": len(short_trades), "correct": len(short_correct),
                      "accuracy": (len(short_correct) / len(short_trades) * 100) if short_trades else 0},
        },
    }
