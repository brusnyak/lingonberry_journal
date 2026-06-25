import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine, BacktestResult
from src.data.loader import DataLoader
from src.features.market_structure import analyze_market_structure

from backtest_nas100_directional_signal import (
    ASSET_TYPE,
    HTF_TIMEFRAME,
    SYMBOL,
    TIMEFRAME,
    add_ema_atr,
    add_session_vwap,
    htf_bias,
    last_directional_break,
    recent_sweep_bias,
    recent_swing_bias,
    round_levels_around,
)


OUTPUT_NAME = "nas100_a_plus_templates"
LONDON_HOURS = (7, 11)
NY_HOURS = (13, 16)


def in_session(ts: pd.Timestamp) -> bool:
    return (
        LONDON_HOURS[0] <= ts.hour < LONDON_HOURS[1]
        or NY_HOURS[0] <= ts.hour < NY_HOURS[1]
    )


def add_reference_levels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date_key"] = out.index.date
    out["prev_day_high"] = out.groupby("date_key")["high"].transform("max").shift(1)
    out["prev_day_low"] = out.groupby("date_key")["low"].transform("min").shift(1)

    asia_highs = []
    asia_lows = []
    current_date = None
    asia_high = None
    asia_low = None
    for ts, row in out.iterrows():
        if ts.date() != current_date:
            current_date = ts.date()
            asia_high = None
            asia_low = None
        if ts.hour < 7:
            asia_high = row["high"] if asia_high is None else max(asia_high, row["high"])
            asia_low = row["low"] if asia_low is None else min(asia_low, row["low"])
        asia_highs.append(asia_high)
        asia_lows.append(asia_low)
    out["asia_high"] = asia_highs
    out["asia_low"] = asia_lows
    return out.drop(columns=["date_key"])


def touched_zone(bar: pd.Series, top: float, bottom: float) -> bool:
    return float(bar["low"]) <= top and float(bar["high"]) >= bottom


def same_side_retest(ms: Dict, bar: pd.Series, direction: str, local_idx: int, lookback: int = 10) -> Dict[str, bool]:
    ob_touch = False
    fvg_touch = False
    for ob in ms.get("order_blocks", []):
        if ob.type != ("bullish" if direction == "long" else "bearish"):
            continue
        if not (local_idx - lookback <= ob.index < local_idx):
            continue
        if touched_zone(bar, ob.top, ob.bottom):
            ob_touch = True
            break
    for fvg in ms.get("fvgs", []):
        if fvg.type != ("bullish" if direction == "long" else "bearish"):
            continue
        if not (local_idx - lookback <= fvg.index < local_idx):
            continue
        if touched_zone(bar, fvg.top, fvg.bottom):
            fvg_touch = True
            break
    return {"ob": ob_touch, "fvg": fvg_touch}


def indicator_bounce(bar: pd.Series, direction: str) -> bool:
    atr = float(bar["atr"])
    tol = max(atr * 0.3, 8.0)
    if direction == "long":
        touched = float(bar["low"]) <= max(float(bar["vwap"]), float(bar["ema20"])) + tol
        return touched and float(bar["close"]) > float(bar["open"]) and float(bar["close"]) >= float(bar["ema20"])
    touched = float(bar["high"]) >= min(float(bar["vwap"]), float(bar["ema20"])) - tol
    return touched and float(bar["close"]) < float(bar["open"]) and float(bar["close"]) <= float(bar["ema20"])


def choose_target(bar: pd.Series, ms: Dict, entry: float, direction: str) -> Optional[float]:
    candidates: List[float] = []
    if direction == "long":
        candidates += [((f.top + f.bottom) / 2) for f in ms.get("fvgs", []) if f.type == "bearish" and ((f.top + f.bottom) / 2) > entry]
        for key in ("asia_high", "prev_day_high"):
            value = bar.get(key)
            if pd.notna(value) and float(value) > entry:
                candidates.append(float(value))
        candidates += [lvl.price for lvl in ms.get("liquidity_levels", []) if not lvl.swept and lvl.price > entry]
        candidates += [level for level in round_levels_around(entry) if level > entry]
        return min(candidates) if candidates else None
    candidates += [((f.top + f.bottom) / 2) for f in ms.get("fvgs", []) if f.type == "bullish" and ((f.top + f.bottom) / 2) < entry]
    for key in ("asia_low", "prev_day_low"):
        value = bar.get(key)
        if pd.notna(value) and float(value) < entry:
            candidates.append(float(value))
    candidates += [lvl.price for lvl in ms.get("liquidity_levels", []) if not lvl.swept and lvl.price < entry]
    candidates += [level for level in round_levels_around(entry) if level < entry]
    return max(candidates) if candidates else None


def choose_stop(ms: Dict, bar: pd.Series, entry: float, direction: str) -> float:
    atr = float(bar["atr"])
    pad = max(atr * 0.2, 4.0)
    if direction == "long":
        candidates = [ob.bottom for ob in ms.get("order_blocks", []) if ob.type == "bullish" and ob.bottom < entry]
        candidates += [lvl.price for lvl in ms.get("liquidity_levels", []) if lvl.price < entry]
        base = max(candidates) if candidates else min(float(bar["low"]), float(bar["ema20"]), float(bar["vwap"]))
        return float(base) - pad
    candidates = [ob.top for ob in ms.get("order_blocks", []) if ob.type == "bearish" and ob.top > entry]
    candidates += [lvl.price for lvl in ms.get("liquidity_levels", []) if lvl.price > entry]
    base = min(candidates) if candidates else max(float(bar["high"]), float(bar["ema20"]), float(bar["vwap"]))
    return float(base) + pad


def build_context(df_5m: pd.DataFrame, df_30m: pd.DataFrame, i: int) -> Optional[Dict]:
    now = df_5m.index[i]
    bar = df_5m.iloc[i]
    if not in_session(now):
        return None
    if pd.isna(bar["atr"]) or float(bar["atr"]) <= 0:
        return None
    if abs(float(bar["close"]) - float(bar["vwap"])) > float(bar["atr"]) * 1.6 and abs(float(bar["close"]) - float(bar["ema20"])) > float(bar["atr"]) * 1.6:
        return None

    window = df_5m.iloc[max(0, i - 50): i + 1].copy()
    if len(window) < 28:
        return None
    ms = analyze_market_structure(
        window,
        swing_period=2,
        break_type="wick",
        fvg_mitigation="partial",
        fvg_mitigation_threshold=0.5,
        fvg_min_gap_pct=0.0,
        fvg_min_gap_atr=0.08,
        volume_filter=False,
        round_level_interval=50,
        premium_discount_lookback=30,
    )
    local_idx = len(window) - 1
    return {
        "time": now,
        "bar": bar,
        "ms": ms,
        "local_idx": local_idx,
        "htf_bias": htf_bias(df_30m, now),
        "local_trend": ms.get("current_trend", "neutral"),
        "swing_bias": recent_swing_bias(ms, local_idx, lookback=10),
        "break_label": last_directional_break(ms, local_idx, lookback=10),
        "sweep_bias": recent_sweep_bias(ms, local_idx, lookback=10),
    }


def decide(ctx: Dict) -> Optional[Dict]:
    break_label = ctx["break_label"]
    if break_label is None:
        return None

    bull_retests = same_side_retest(ctx["ms"], ctx["bar"], "long", ctx["local_idx"])
    bear_retests = same_side_retest(ctx["ms"], ctx["bar"], "short", ctx["local_idx"])
    bull_bounce = indicator_bounce(ctx["bar"], "long")
    bear_bounce = indicator_bounce(ctx["bar"], "short")

    bull_cont = (
        ctx["htf_bias"] == "bullish"
        and ctx["local_trend"] == "bullish"
        and ctx["swing_bias"] == "bullish"
        and break_label in {"BOS:bullish", "CHoCH:bullish"}
        and (bull_retests["ob"] or bull_retests["fvg"])
        and bull_bounce
    )
    bull_reversal = (
        break_label == "CHoCH:bullish"
        and ctx["sweep_bias"] == "bullish"
        and bull_retests["ob"]
        and bull_bounce
    )
    if bull_cont or bull_reversal:
        return {
            "direction": "long",
            "template": "bull_cont_ob" if bull_cont else "bull_sweep_choch",
            "retest": bull_retests,
            "bounce": bull_bounce,
        }

    bear_cont = (
        ctx["htf_bias"] == "bearish"
        and ctx["local_trend"] == "bearish"
        and ctx["swing_bias"] == "bearish"
        and break_label in {"BOS:bearish", "CHoCH:bearish"}
        and (bear_retests["ob"] or bear_retests["fvg"])
        and bear_bounce
    )
    bear_reversal = (
        break_label == "CHoCH:bearish"
        and ctx["sweep_bias"] == "bearish"
        and bear_retests["ob"]
        and bear_bounce
    )
    if bear_cont or bear_reversal:
        return {
            "direction": "short",
            "template": "bear_cont_ob" if bear_cont else "bear_sweep_choch",
            "retest": bear_retests,
            "bounce": bear_bounce,
        }

    return None


def run(limit_5m: int = 4000, limit_30m: int = 2000) -> Dict:
    loader = DataLoader()
    df_5m = loader.load(SYMBOL, TIMEFRAME, limit=limit_5m, prefer_parquet=True).copy()
    df_5m = add_reference_levels(add_ema_atr(add_session_vwap(df_5m)))
    df_30m = add_ema_atr(add_session_vwap(loader.load(SYMBOL, HTF_TIMEFRAME, limit=limit_30m, prefer_parquet=True).copy()))

    engine = BacktestEngine(initial_capital=20000.0, commission=0.0, slippage=0.0, risk_per_trade=0.01, position_sizing="risk_pct")
    trade_meta: List[Dict] = []
    open_meta: Optional[Dict] = None
    prev_closed_count = 0
    cooldown_until = -1

    for i in range(70, len(df_5m)):
        row = df_5m.iloc[i]
        now = df_5m.index[i]
        engine.update(now, float(row["high"]), float(row["low"]), float(row["close"]))

        if len(engine.closed_trades) > prev_closed_count:
            prev_closed_count = len(engine.closed_trades)
            if open_meta is not None:
                closed = engine.closed_trades[-1]
                open_meta["exit_reason"] = closed.exit_reason
                open_meta["pnl"] = closed.pnl
                open_meta["pnl_pct"] = closed.pnl_pct
                trade_meta.append(open_meta)
                open_meta = None
                cooldown_until = i + 2

        if engine.current_trade is not None and open_meta is not None:
            if i - open_meta["entry_idx"] >= 12:
                engine.close_trade(now, float(row["close"]), "time_exit")
                prev_closed_count = len(engine.closed_trades)
                closed = engine.closed_trades[-1]
                open_meta["exit_reason"] = closed.exit_reason
                open_meta["pnl"] = closed.pnl
                open_meta["pnl_pct"] = closed.pnl_pct
                trade_meta.append(open_meta)
                open_meta = None
                cooldown_until = i + 2
            continue

        if i <= cooldown_until:
            continue

        ctx = build_context(df_5m, df_30m, i)
        if ctx is None:
            continue
        decision = decide(ctx)
        if decision is None:
            continue

        entry = float(ctx["bar"]["close"])
        direction = decision["direction"]
        stop = choose_stop(ctx["ms"], ctx["bar"], entry, direction)
        target = choose_target(ctx["bar"], ctx["ms"], entry, direction)
        if target is None:
            target = entry + (float(ctx["bar"]["atr"]) * 2.0 if direction == "long" else -float(ctx["bar"]["atr"]) * 2.0)

        risk = (entry - stop) if direction == "long" else (stop - entry)
        reward = (target - entry) if direction == "long" else (entry - target)
        if risk <= 0 or reward <= 0 or reward / risk < 1.2:
            continue

        engine.open_trade(ctx["time"], entry, direction=direction, stop_loss=float(stop), take_profit=float(target))
        open_meta = {
            "entry_idx": i,
            "template": decision["template"],
            "htf_bias": ctx["htf_bias"],
            "local_trend": ctx["local_trend"],
            "swing_bias": ctx["swing_bias"],
            "break_label": ctx["break_label"],
            "sweep_bias": ctx["sweep_bias"],
            "retest": decision["retest"],
            "planned_rr": reward / risk,
            "session": "london" if LONDON_HOURS[0] <= ctx["time"].hour < LONDON_HOURS[1] else "ny",
        }

    if engine.current_trade is not None and open_meta is not None:
        engine.close_trade(df_5m.index[-1], float(df_5m["close"].iloc[-1]), "end_of_data")
        closed = engine.closed_trades[-1]
        open_meta["exit_reason"] = closed.exit_reason
        open_meta["pnl"] = closed.pnl
        open_meta["pnl_pct"] = closed.pnl_pct
        trade_meta.append(open_meta)

    trades = engine.closed_trades
    equity_series = pd.Series([eq[1] for eq in engine.equity_curve], index=[eq[0] for eq in engine.equity_curve]) if engine.equity_curve else pd.Series(dtype=float)
    result_obj = BacktestResult(trades=trades, equity_curve=equity_series, initial_capital=engine.initial_capital, final_capital=engine.capital)

    out_trades = []
    for idx, trade in enumerate(trades):
        meta = trade_meta[idx] if idx < len(trade_meta) else {}
        out_trades.append({
            "id": f"nas100-a-plus-{idx}",
            "direction": trade.direction,
            "entry_time": trade.entry_time.isoformat(),
            "entry_price": trade.entry_price,
            "stop_loss": trade.stop_loss,
            "take_profit": trade.take_profit,
            "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
            "exit_price": trade.exit_price,
            "pnl": trade.pnl,
            "pnl_pct": trade.pnl_pct,
            "status": "done",
            "notes": f"A+ template {meta.get('template', '')}",
            "tags": ["strategy:nas100_a_plus_templates"],
            "meta": meta,
        })

    result = {
        "id": OUTPUT_NAME,
        "name": "NAS100 A+ Templates",
        "symbol": SYMBOL,
        "asset_type": ASSET_TYPE,
        "timeframe": TIMEFRAME,
        "strategy": "a_plus_templates",
        "trades": out_trades,
        "summary": {
            "total_trades": len(trades),
            "wins": sum(1 for t in trades if t.pnl is not None and t.pnl > 0),
            "win_rate": (sum(1 for t in trades if t.pnl is not None and t.pnl > 0) / len(trades) * 100) if trades else 0.0,
            "return_pct": ((engine.capital - engine.initial_capital) / engine.initial_capital * 100),
            "final_capital": engine.capital,
            "max_drawdown": result_obj.max_drawdown,
            "profit_factor": result_obj.profit_factor,
            "avg_rr": result_obj.avg_rr,
        },
        "monte_carlo": result_obj.monte_carlo_simulation(n_simulations=500),
    }

    out_dir = Path(__file__).parents[2] / "data" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{OUTPUT_NAME}.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps({"output": str(out_path), "summary": result["summary"]}, indent=2))
    return result


if __name__ == "__main__":
    run()
