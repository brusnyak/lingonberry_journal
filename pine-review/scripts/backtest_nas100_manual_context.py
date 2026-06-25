import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine, BacktestResult
from src.data.loader import DataLoader
from src.features.market_structure import analyze_market_structure

try:
    from backtest_nas100_directional_signal import (
        ASSET_TYPE,
        HTF_TIMEFRAME,
        SYMBOL,
        TIMEFRAME,
        add_ema_atr,
        add_session_vwap,
        find_stop_from_structure,
        find_target_from_structure,
        htf_bias,
        in_ny_news_caution,
        last_directional_break,
        recent_sweep_bias,
        recent_swing_bias,
        round_levels_around,
        zone_retest_bias,
    )
except ModuleNotFoundError:
    from backend.scripts.backtest_nas100_directional_signal import (
        ASSET_TYPE,
        HTF_TIMEFRAME,
        SYMBOL,
        TIMEFRAME,
        add_ema_atr,
        add_session_vwap,
        find_stop_from_structure,
        find_target_from_structure,
        htf_bias,
        in_ny_news_caution,
        last_directional_break,
        recent_sweep_bias,
        recent_swing_bias,
        round_levels_around,
        zone_retest_bias,
    )


OUTPUT_NAME = "nas100_manual_context"
LONDON_HOURS = (7, 11)
NY_HOURS = (13, 16)


def in_manual_session(ts: pd.Timestamp) -> bool:
    return (
        LONDON_HOURS[0] <= ts.hour < LONDON_HOURS[1]
        or NY_HOURS[0] <= ts.hour < NY_HOURS[1]
    )


def add_intraday_reference_levels(df: pd.DataFrame) -> pd.DataFrame:
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


def candle_bounce_bias(bar: pd.Series) -> str:
    close = float(bar["close"])
    open_ = float(bar["open"])
    vwap = float(bar["vwap"])
    ema = float(bar["ema20"])
    atr = float(bar["atr"])
    tolerance = max(atr * 0.25, 8.0)

    touched_lower = float(bar["low"]) <= max(vwap, ema) + tolerance
    touched_upper = float(bar["high"]) >= min(vwap, ema) - tolerance

    if close > open_ and close >= vwap and close >= ema and touched_lower:
        return "bullish"
    if close < open_ and close <= vwap and close <= ema and touched_upper:
        return "bearish"
    return "neutral"


def choose_manual_target(bar: pd.Series, ms: Dict, entry: float, direction: str) -> Optional[float]:
    candidates: List[float] = []
    structure_target = find_target_from_structure(ms, entry, direction, round_levels_around(entry))
    if structure_target is not None:
        candidates.append(structure_target)

    if direction == "long":
        for key in ("asia_high", "prev_day_high"):
            val = bar.get(key)
            if pd.notna(val) and float(val) > entry:
                candidates.append(float(val))
        candidates.extend(level for level in round_levels_around(entry) if level > entry)
        return min(candidates) if candidates else None

    for key in ("asia_low", "prev_day_low"):
        val = bar.get(key)
        if pd.notna(val) and float(val) < entry:
            candidates.append(float(val))
    candidates.extend(level for level in round_levels_around(entry) if level < entry)
    return max(candidates) if candidates else None


def context_for_bar(df_5m: pd.DataFrame, df_30m: pd.DataFrame, i: int) -> Optional[Dict]:
    now = df_5m.index[i]
    bar = df_5m.iloc[i]
    if pd.isna(bar["atr"]) or float(bar["atr"]) <= 0:
        return None

    near_indicator = (
        abs(float(bar["close"]) - float(bar["vwap"])) <= float(bar["atr"]) * 1.4
        or abs(float(bar["close"]) - float(bar["ema20"])) <= float(bar["atr"]) * 1.4
    )
    if not near_indicator and not in_manual_session(now):
        return None

    window = df_5m.iloc[max(0, i - 40): i + 1].copy()
    if len(window) < 24:
        return None
    ms = analyze_market_structure(
        window,
        swing_period=3,
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
        "swing_bias": recent_swing_bias(ms, local_idx),
        "break_label": last_directional_break(ms, local_idx),
        "sweep_bias": recent_sweep_bias(ms, local_idx),
        "retest_bias": zone_retest_bias(ms, bar, local_idx),
        "bounce_bias": candle_bounce_bias(bar),
        "session_ok": in_manual_session(now),
        "news": in_ny_news_caution(now),
        "local_trend": ms.get("current_trend", "neutral"),
    }


def decide_manual_context(ctx: Dict) -> Optional[str]:
    if not ctx["session_ok"]:
        return None

    bullish_checks = [
        ctx["htf_bias"] == "bullish",
        ctx["local_trend"] == "bullish",
        ctx["break_label"] in {"CHoCH:bullish", "BOS:bullish"},
        ctx["retest_bias"] == "bullish",
        ctx["bounce_bias"] == "bullish",
        ctx["swing_bias"] == "bullish",
    ]
    bearish_checks = [
        ctx["htf_bias"] == "bearish",
        ctx["local_trend"] == "bearish",
        ctx["break_label"] in {"CHoCH:bearish", "BOS:bearish"},
        ctx["retest_bias"] == "bearish",
        ctx["bounce_bias"] == "bearish",
        ctx["swing_bias"] == "bearish",
    ]

    if ctx["news"]:
        bullish_checks[4] = False
        bearish_checks[4] = False

    if sum(bullish_checks) >= 4 and ctx["retest_bias"] == "bullish":
        return "long"
    if (
        ctx["htf_bias"] == "bullish"
        and ctx["sweep_bias"] == "bullish"
        and ctx["break_label"] in {"CHoCH:bullish", "BOS:bullish"}
        and ctx["bounce_bias"] == "bullish"
    ):
        return "long"

    if sum(bearish_checks) >= 4 and ctx["retest_bias"] == "bearish":
        return "short"
    if (
        ctx["htf_bias"] == "bearish"
        and ctx["sweep_bias"] == "bearish"
        and ctx["break_label"] in {"CHoCH:bearish", "BOS:bearish"}
        and ctx["bounce_bias"] == "bearish"
    ):
        return "short"

    return None


def run(limit_5m: int = 12000, limit_30m: int = 5000) -> Dict:
    loader = DataLoader()
    df_5m = loader.load(SYMBOL, TIMEFRAME, limit=limit_5m, prefer_parquet=True).copy()
    df_5m = add_intraday_reference_levels(add_ema_atr(add_session_vwap(df_5m)))
    df_30m = add_ema_atr(add_session_vwap(loader.load(SYMBOL, HTF_TIMEFRAME, limit=limit_30m, prefer_parquet=True).copy()))

    engine = BacktestEngine(
        initial_capital=20000.0,
        commission=0.0,
        slippage=0.0,
        risk_per_trade=0.01,
        position_sizing="risk_pct",
    )

    trade_meta: List[Dict] = []
    open_meta: Optional[Dict] = None
    prev_closed_count = 0
    cooldown_until = -1

    for i in range(60, len(df_5m)):
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

        ctx = context_for_bar(df_5m, df_30m, i)
        if ctx is None:
            continue
        direction = decide_manual_context(ctx)
        if direction is None:
            continue

        entry = float(ctx["bar"]["close"])
        target = choose_manual_target(ctx["bar"], ctx["ms"], entry, direction)
        stop = find_stop_from_structure(ctx["ms"], ctx["bar"], entry, direction, float(ctx["bar"]["atr"]))
        if target is None:
            target = entry + (float(ctx["bar"]["atr"]) * 2.0 if direction == "long" else -float(ctx["bar"]["atr"]) * 2.0)

        risk = (entry - stop) if direction == "long" else (stop - entry)
        reward = (target - entry) if direction == "long" else (entry - target)
        if risk <= 0 or reward <= 0 or (reward / risk) < 1.1:
            continue

        engine.open_trade(now, entry, direction=direction, stop_loss=float(stop), take_profit=float(target))
        open_meta = {
            "entry_idx": i,
            "setup": "manual_context",
            "htf_bias": ctx["htf_bias"],
            "local_trend": ctx["local_trend"],
            "swing_bias": ctx["swing_bias"],
            "break_label": ctx["break_label"],
            "sweep_bias": ctx["sweep_bias"],
            "retest_bias": ctx["retest_bias"],
            "bounce_bias": ctx["bounce_bias"],
            "session_ok": ctx["session_ok"],
            "news": ctx["news"],
            "asia_high": None if pd.isna(ctx["bar"].get("asia_high")) else float(ctx["bar"].get("asia_high")),
            "asia_low": None if pd.isna(ctx["bar"].get("asia_low")) else float(ctx["bar"].get("asia_low")),
            "prev_day_high": None if pd.isna(ctx["bar"].get("prev_day_high")) else float(ctx["bar"].get("prev_day_high")),
            "prev_day_low": None if pd.isna(ctx["bar"].get("prev_day_low")) else float(ctx["bar"].get("prev_day_low")),
            "planned_rr": reward / risk,
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
          "id": f"nas100-manual-{idx}",
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
          "notes": f"Manual context {trade.direction}",
          "tags": ["strategy:nas100_manual_context"],
          "meta": meta,
      })

    result = {
        "id": OUTPUT_NAME,
        "name": "NAS100 Manual Context",
        "symbol": SYMBOL,
        "asset_type": ASSET_TYPE,
        "timeframe": TIMEFRAME,
        "strategy": "manual_context",
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
