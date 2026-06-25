import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine, BacktestResult
from src.data.loader import DataLoader
from src.features.market_structure import analyze_market_structure
from src.features.technicals import calculate_atr


SYMBOL = "USATECHIDXUSD"
ASSET_TYPE = "indeces"
TIMEFRAME = "5"
HTF_TIMEFRAME = "30"
OUTPUT_NAME = "nas100_directional_signal"
PRIMARY_KILL_ZONES = ((8, 10), (13, 15))
NY_NEWS_CAUTION = ((13, 20), (13, 40))


def add_session_vwap(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    date_key = out.index.date
    hlc3 = (out["high"] + out["low"] + out["close"]) / 3
    out["cum_pv"] = (hlc3 * out["volume"]).groupby(date_key).cumsum()
    out["cum_vol"] = out["volume"].groupby(date_key).cumsum().replace(0, 1)
    out["vwap"] = out["cum_pv"] / out["cum_vol"]
    return out.drop(columns=["cum_pv", "cum_vol"])


def add_ema_atr(df: pd.DataFrame, ema_length: int = 20) -> pd.DataFrame:
    out = df.copy()
    out["ema20"] = out["close"].ewm(span=ema_length, adjust=False).mean()
    out["atr"] = calculate_atr(out["high"], out["low"], out["close"], period=14)
    return out


def in_primary_kill_zone(ts: pd.Timestamp) -> bool:
    hour = ts.hour
    return any(start <= hour < end for start, end in PRIMARY_KILL_ZONES)


def in_ny_news_caution(ts: pd.Timestamp) -> bool:
    hm = (ts.hour, ts.minute)
    return NY_NEWS_CAUTION[0] <= hm < NY_NEWS_CAUTION[1]


def round_levels_around(price: float, step: int = 50, count: int = 6) -> List[float]:
    center = round(price / step) * step
    return [center + step * offset for offset in range(-count, count + 1)]


def last_directional_break(ms: Dict, local_idx: int, lookback: int = 8) -> Optional[str]:
    recent = [b for b in ms.get("structure_breaks", []) if local_idx - lookback <= b.index <= local_idx]
    if not recent:
        return None
    return f"{recent[-1].type}:{recent[-1].direction}"


def recent_swing_bias(ms: Dict, local_idx: int, lookback: int = 8) -> str:
    labels = [
        label for idx, label in ms.get("swing_labels", {}).items()
        if local_idx - lookback <= idx <= local_idx
    ]
    bull = sum(1 for label in labels if label in {"HH", "HL"})
    bear = sum(1 for label in labels if label in {"LH", "LL"})
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def recent_sweep_bias(ms: Dict, local_idx: int, lookback: int = 8) -> str:
    bull = 0
    bear = 0
    for lvl in ms.get("liquidity_levels", []):
        swept_idx = getattr(lvl, "swept_index", None)
        if swept_idx is None:
            continue
        if not (local_idx - lookback <= swept_idx <= local_idx):
            continue
        if lvl.type == "low":
            bull += 1
        if lvl.type == "high":
            bear += 1
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def zone_retest_bias(ms: Dict, bar: pd.Series, local_idx: int, lookback: int = 20) -> str:
    bull = 0
    bear = 0
    for ob in ms.get("order_blocks", []):
        if not (local_idx - lookback <= ob.index < local_idx):
            continue
        touched = float(bar["low"]) <= ob.top and float(bar["high"]) >= ob.bottom
        if not touched:
            continue
        if ob.type == "bullish":
            bull += 1
        else:
            bear += 1
    for fvg in ms.get("fvgs", []):
        if not (local_idx - lookback <= fvg.index < local_idx):
            continue
        touched = float(bar["low"]) <= fvg.top and float(bar["high"]) >= fvg.bottom
        if not touched:
            continue
        if fvg.type == "bullish":
            bull += 1
        else:
            bear += 1
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def find_target_from_structure(ms: Dict, entry_price: float, direction: str, round_levels: List[float]) -> Optional[float]:
    candidates: List[float] = []
    if direction == "long":
        candidates += [lvl.price for lvl in ms.get("liquidity_levels", []) if not lvl.swept and lvl.price > entry_price]
        candidates += [((f.top + f.bottom) / 2) for f in ms.get("fvgs", []) if f.type == "bearish" and ((f.top + f.bottom) / 2) > entry_price]
        candidates += [level for level in round_levels if level > entry_price]
        return min(candidates) if candidates else None
    candidates += [lvl.price for lvl in ms.get("liquidity_levels", []) if not lvl.swept and lvl.price < entry_price]
    candidates += [((f.top + f.bottom) / 2) for f in ms.get("fvgs", []) if f.type == "bullish" and ((f.top + f.bottom) / 2) < entry_price]
    candidates += [level for level in round_levels if level < entry_price]
    return max(candidates) if candidates else None


def find_stop_from_structure(ms: Dict, bar: pd.Series, entry_price: float, direction: str, atr: float) -> float:
    if direction == "long":
        lows = [lvl.price for lvl in ms.get("liquidity_levels", []) if lvl.price < entry_price]
        structure_stop = max(lows) if lows else min(float(bar["low"]), float(bar["vwap"]), float(bar["ema20"]))
        return structure_stop - max(atr * 0.2, 4.0)
    highs = [lvl.price for lvl in ms.get("liquidity_levels", []) if lvl.price > entry_price]
    structure_stop = min(highs) if highs else max(float(bar["high"]), float(bar["vwap"]), float(bar["ema20"]))
    return structure_stop + max(atr * 0.2, 4.0)


def htf_bias(df_30m: pd.DataFrame, now: pd.Timestamp) -> str:
    idx = df_30m.index.searchsorted(now, side="right") - 1
    if idx < 20:
        return "neutral"
    row = df_30m.iloc[idx]
    if float(row["close"]) > float(row["vwap"]) and float(row["close"]) > float(row["ema20"]):
        return "bullish"
    if float(row["close"]) < float(row["vwap"]) and float(row["close"]) < float(row["ema20"]):
        return "bearish"
    return "neutral"


def score_direction(
    df_5m: pd.DataFrame,
    df_30m: pd.DataFrame,
    i: int,
) -> Tuple[Optional[str], Dict[str, object]]:
    now = df_5m.index[i]
    bar = df_5m.iloc[i]
    window = df_5m.iloc[max(0, i - 36) : i + 1].copy()
    if len(window) < 24:
        return None, {}

    ms = analyze_market_structure(window, swing_period=3, volume_filter=False, round_level_interval=50, premium_discount_lookback=30)
    local_idx = len(window) - 1
    score = 0.0
    reasons: List[str] = []

    higher_tf = htf_bias(df_30m, now)
    if higher_tf == "bullish":
        score += 2.0
        reasons.append("htf_bullish")
    elif higher_tf == "bearish":
        score -= 2.0
        reasons.append("htf_bearish")

    local_trend = ms.get("current_trend", "neutral")
    if local_trend == "bullish":
        score += 1.5
        reasons.append("local_trend_bullish")
    elif local_trend == "bearish":
        score -= 1.5
        reasons.append("local_trend_bearish")

    swing_bias = recent_swing_bias(ms, local_idx)
    if swing_bias == "bullish":
        score += 1.0
        reasons.append("hh_hl_bias")
    elif swing_bias == "bearish":
        score -= 1.0
        reasons.append("ll_lh_bias")

    last_break = last_directional_break(ms, local_idx)
    if last_break == "BOS:bullish":
        score += 2.0
        reasons.append("recent_bull_bos")
    elif last_break == "CHoCH:bullish":
        score += 2.5
        reasons.append("recent_bull_choch")
    elif last_break == "BOS:bearish":
        score -= 2.0
        reasons.append("recent_bear_bos")
    elif last_break == "CHoCH:bearish":
        score -= 2.5
        reasons.append("recent_bear_choch")

    sweep_bias = recent_sweep_bias(ms, local_idx)
    if sweep_bias == "bullish":
        score += 1.5
        reasons.append("recent_low_sweep")
    elif sweep_bias == "bearish":
        score -= 1.5
        reasons.append("recent_high_sweep")

    retest_bias = zone_retest_bias(ms, bar, local_idx)
    if retest_bias == "bullish":
        score += 1.0
        reasons.append("bullish_ob_fvg_retest")
    elif retest_bias == "bearish":
        score -= 1.0
        reasons.append("bearish_ob_fvg_retest")

    if float(bar["close"]) > float(bar["vwap"]) and float(bar["close"]) > float(bar["ema20"]):
        score += 0.75
        reasons.append("price_above_vwap_ema")
    elif float(bar["close"]) < float(bar["vwap"]) and float(bar["close"]) < float(bar["ema20"]):
        score -= 0.75
        reasons.append("price_below_vwap_ema")

    round_levels = round_levels_around(float(bar["close"]))
    nearest_round = min(round_levels, key=lambda x: abs(x - float(bar["close"])))
    if abs(float(bar["close"]) - nearest_round) <= max(float(bar["atr"]) * 0.5, 12.0):
        score += 0.25 if score >= 0 else -0.25
        reasons.append("near_round_level")

    if in_primary_kill_zone(now):
        score += 0.5 if score >= 0 else -0.5
        reasons.append("kill_zone")

    if in_ny_news_caution(now):
        score *= 0.6
        reasons.append("ny_news_caution")

    direction = None
    if score >= 3.5:
        direction = "long"
    elif score <= -3.5:
        direction = "short"

    meta = {
        "score": score,
        "reasons": reasons,
        "htf_bias": higher_tf,
        "local_trend": local_trend,
        "swing_bias": swing_bias,
        "last_break": last_break,
        "sweep_bias": sweep_bias,
        "retest_bias": retest_bias,
        "kill_zone": in_primary_kill_zone(now),
        "ny_news_caution": in_ny_news_caution(now),
        "round_level": nearest_round,
        "market_structure": ms,
    }
    return direction, meta


def run(limit_5m: int = 8000, limit_30m: int = 4000) -> Dict:
    loader = DataLoader()
    df_5m = add_ema_atr(add_session_vwap(loader.load(SYMBOL, TIMEFRAME, limit=limit_5m, prefer_parquet=True).copy()))
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
    max_bars_in_trade = 12

    for i in range(50, len(df_5m)):
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
            if i - open_meta["entry_idx"] >= max_bars_in_trade:
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
        if pd.isna(row["atr"]) or float(row["atr"]) <= 0:
            continue

        near_context = (
            abs(float(row["close"]) - float(row["vwap"])) <= float(row["atr"]) * 1.5
            or abs(float(row["close"]) - float(row["ema20"])) <= float(row["atr"]) * 1.5
            or in_primary_kill_zone(now)
        )
        if not near_context:
            continue

        direction, meta = score_direction(df_5m, df_30m, i)
        if direction is None:
            continue

        ms = meta.pop("market_structure")
        entry = float(row["close"])
        round_levels = round_levels_around(entry)
        target = find_target_from_structure(ms, entry, direction, round_levels)
        stop = find_stop_from_structure(ms, row, entry, direction, float(row["atr"]))
        if target is None:
            target = entry + (float(row["atr"]) * 2.0 if direction == "long" else -float(row["atr"]) * 2.0)

        risk = (entry - stop) if direction == "long" else (stop - entry)
        reward = (target - entry) if direction == "long" else (entry - target)
        if risk <= 0 or reward <= 0:
            continue
        if reward / risk < 1.0:
            continue

        engine.open_trade(now, entry, direction=direction, stop_loss=float(stop), take_profit=float(target))
        open_meta = {
            "entry_idx": i,
            "setup": "directional_signal",
            "direction_score": meta["score"],
            "reasons": meta["reasons"],
            "htf_bias": meta["htf_bias"],
            "local_trend": meta["local_trend"],
            "swing_bias": meta["swing_bias"],
            "last_break": meta["last_break"],
            "sweep_bias": meta["sweep_bias"],
            "retest_bias": meta["retest_bias"],
            "kill_zone": meta["kill_zone"],
            "ny_news_caution": meta["ny_news_caution"],
            "round_level": meta["round_level"],
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
    equity_series = pd.Series(
        [eq[1] for eq in engine.equity_curve],
        index=[eq[0] for eq in engine.equity_curve],
    ) if engine.equity_curve else pd.Series(dtype=float)
    result_obj = BacktestResult(
        trades=trades,
        equity_curve=equity_series,
        initial_capital=engine.initial_capital,
        final_capital=engine.capital,
    )

    backtest_trades = []
    for idx, trade in enumerate(trades):
        meta = trade_meta[idx] if idx < len(trade_meta) else {}
        backtest_trades.append(
            {
                "id": f"nas100-dir-{idx}",
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
                "notes": f"Directional {trade.direction} score {meta.get('direction_score', 0):.2f}",
                "tags": [
                    "strategy:nas100_directional_signal",
                    f"htf:{meta.get('htf_bias', 'neutral')}",
                    f"break:{meta.get('last_break', 'none')}",
                ],
                "meta": meta,
            }
        )

    result = {
        "id": OUTPUT_NAME,
        "name": "NAS100 Directional Signal",
        "symbol": SYMBOL,
        "asset_type": ASSET_TYPE,
        "timeframe": TIMEFRAME,
        "strategy": "directional_signal",
        "trades": backtest_trades,
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

    output_dir = Path(__file__).parents[2] / "data" / "backtests"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{OUTPUT_NAME}.json"
    output_path.write_text(json.dumps(result, indent=2))
    print(json.dumps({"output": str(output_path), "summary": result["summary"]}, indent=2))
    return result


if __name__ == "__main__":
    run()
