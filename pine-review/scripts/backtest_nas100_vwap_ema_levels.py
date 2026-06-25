import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine, BacktestResult
from src.data.loader import DataLoader
from src.features.technicals import calculate_atr


SYMBOL = "USATECHIDXUSD"
TIMEFRAME = "5"
ASSET_TYPE = "indeces"
OUTPUT_NAME = "nas100_vwap_ema_bounce"
KILL_ZONES = ((8, 10), (13, 15))


def add_session_vwap(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    date_key = out.index.date
    hlc3 = (out["high"] + out["low"] + out["close"]) / 3
    out["cum_pv"] = (hlc3 * out["volume"]).groupby(date_key).cumsum()
    out["cum_vol"] = out["volume"].groupby(date_key).cumsum().replace(0, 1)
    out["vwap"] = out["cum_pv"] / out["cum_vol"]
    return out.drop(columns=["cum_pv", "cum_vol"])


def add_ema_and_atr(df: pd.DataFrame, ema_length: int = 20) -> pd.DataFrame:
    out = df.copy()
    out["ema20"] = out["close"].ewm(span=ema_length, adjust=False).mean()
    out["atr"] = calculate_atr(out["high"], out["low"], out["close"], period=14)
    return out


def nearest_round_level(price: float, step: int = 50) -> float:
    return round(price / step) * step


def round_levels_around(price: float, step: int = 50, count: int = 5) -> List[float]:
    center = nearest_round_level(price, step=step)
    return [center + step * offset for offset in range(-count, count + 1)]


def nearest_level(price: float, levels: List[float]) -> Optional[float]:
    if not levels:
        return None
    return min(levels, key=lambda level: abs(level - price))


def next_level(levels: List[float], price: float, direction: str) -> Optional[float]:
    if direction == "long":
        higher = [level for level in levels if level > price]
        return min(higher) if higher else None
    lower = [level for level in levels if level < price]
    return max(lower) if lower else None


def in_kill_zone(ts: pd.Timestamp) -> Optional[str]:
    hour = ts.hour
    for start, end in KILL_ZONES:
        if start <= hour < end:
            return f"{start:02d}-{end:02d}"
    return None


def bars_in_trend(df: pd.DataFrame, end_idx: int, direction: str, lookback: int = 3) -> bool:
    start = max(0, end_idx - lookback + 1)
    window = df.iloc[start : end_idx + 1]
    if len(window) < lookback:
        return False
    if direction == "long":
        return bool((window["close"] > window["vwap"]).all() and (window["close"] > window["ema20"]).all())
    return bool((window["close"] < window["vwap"]).all() and (window["close"] < window["ema20"]).all())


def build_zone(row: pd.Series, round_level: float) -> Tuple[float, float]:
    zone_lo = min(float(row["vwap"]), float(row["ema20"]), round_level)
    zone_hi = max(float(row["vwap"]), float(row["ema20"]), round_level)
    return zone_lo, zone_hi


def long_retest_signal(df: pd.DataFrame, i: int, round_level: float, tolerance: float) -> Tuple[bool, Dict[str, float]]:
    if i < 5:
        return False, {}
    touch = df.iloc[i - 2]
    reclaim = df.iloc[i - 1]
    entry = df.iloc[i]

    if not bars_in_trend(df, i - 3, "long", lookback=3):
        return False, {}

    zone_lo, zone_hi = build_zone(reclaim, round_level)
    if float(touch["low"]) > zone_hi + tolerance:
        return False, {}
    if float(reclaim["close"]) <= max(float(reclaim["vwap"]), float(reclaim["ema20"]), round_level):
        return False, {}
    if float(reclaim["close"]) <= float(reclaim["open"]):
        return False, {}
    if float(reclaim["high"]) <= float(touch["high"]):
        return False, {}
    if float(entry["low"]) > float(reclaim["close"]) + tolerance:
        return False, {}
    if float(entry["low"]) < zone_lo - tolerance:
        return False, {}
    if float(entry["close"]) <= max(float(entry["vwap"]), float(entry["ema20"])):
        return False, {}
    if float(entry["close"]) <= float(entry["open"]):
        return False, {}

    return True, {
        "touch_price": float(touch["low"]),
        "zone_lo": zone_lo,
        "zone_hi": zone_hi,
        "signal_source": "vwap_retest" if abs(float(reclaim["vwap"]) - round_level) <= abs(float(reclaim["ema20"]) - round_level) else "ema20_retest",
    }


def short_retest_signal(df: pd.DataFrame, i: int, round_level: float, tolerance: float) -> Tuple[bool, Dict[str, float]]:
    if i < 5:
        return False, {}
    touch = df.iloc[i - 2]
    reclaim = df.iloc[i - 1]
    entry = df.iloc[i]

    if not bars_in_trend(df, i - 3, "short", lookback=3):
        return False, {}

    zone_lo, zone_hi = build_zone(reclaim, round_level)
    if float(touch["high"]) < zone_lo - tolerance:
        return False, {}
    if float(reclaim["close"]) >= min(float(reclaim["vwap"]), float(reclaim["ema20"]), round_level):
        return False, {}
    if float(reclaim["close"]) >= float(reclaim["open"]):
        return False, {}
    if float(reclaim["low"]) >= float(touch["low"]):
        return False, {}
    if float(entry["high"]) < float(reclaim["close"]) - tolerance:
        return False, {}
    if float(entry["high"]) > zone_hi + tolerance:
        return False, {}
    if float(entry["close"]) >= min(float(entry["vwap"]), float(entry["ema20"])):
        return False, {}
    if float(entry["close"]) >= float(entry["open"]):
        return False, {}

    return True, {
        "touch_price": float(touch["high"]),
        "zone_lo": zone_lo,
        "zone_hi": zone_hi,
        "signal_source": "vwap_retest" if abs(float(reclaim["vwap"]) - round_level) <= abs(float(reclaim["ema20"]) - round_level) else "ema20_retest",
    }


def run(limit: int = 30000) -> Dict:
    loader = DataLoader()
    df = loader.load(SYMBOL, TIMEFRAME, limit=limit, prefer_parquet=True).copy()
    df = add_session_vwap(df)
    df = add_ema_and_atr(df)

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
    min_rr = 1.25
    traded_killzones: set[tuple[str, str]] = set()

    for i in range(25, len(df)):
        row = df.iloc[i]
        now = df.index[i]
        session_day = now.strftime("%Y-%m-%d")

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

        if i == 25 or df.index[i - 1].date() != now.date():
            traded_killzones.clear()

        killzone = in_kill_zone(now)
        if killzone is None:
            continue
        if (session_day, killzone) in traded_killzones:
            continue

        atr = row.get("atr")
        if pd.isna(atr) or float(atr) <= 0:
            continue

        tolerance = max(float(atr) * 0.22, 6.0)
        nearby_levels = round_levels_around(float(row["close"]), step=50, count=5)
        entry_round = nearest_level(float(row["close"]), nearby_levels)
        round_is_near = entry_round is not None and abs(float(row["close"]) - entry_round) <= max(float(atr) * 0.5, 12.0)
        if not round_is_near or entry_round is None:
            continue

        direction: Optional[str] = None
        signal_meta: Dict[str, float] = {}

        long_ok, long_meta = long_retest_signal(df, i, entry_round, tolerance=tolerance)
        short_ok, short_meta = short_retest_signal(df, i, entry_round, tolerance=tolerance)

        if long_ok:
            direction = "long"
            signal_meta = long_meta
        elif short_ok:
            direction = "short"
            signal_meta = short_meta
        else:
            continue

        entry = float(row["close"])
        if direction == "long":
            stop = min(
                float(df.iloc[i - 2]["low"]),
                float(df.iloc[i - 1]["low"]),
                float(df.iloc[i]["low"]),
                signal_meta["zone_lo"],
            ) - max(float(atr) * 0.18, 4.0)
            risk = entry - stop
            target = next_level(sorted(set(nearby_levels + [entry_round + 50, entry_round + 100, entry_round + 150])), entry, direction="long")
            if target is None or target <= entry:
                continue
        else:
            stop = max(
                float(df.iloc[i - 2]["high"]),
                float(df.iloc[i - 1]["high"]),
                float(df.iloc[i]["high"]),
                signal_meta["zone_hi"],
            ) + max(float(atr) * 0.18, 4.0)
            risk = stop - entry
            target = next_level(sorted(set(nearby_levels + [entry_round - 50, entry_round - 100, entry_round - 150])), entry, direction="short")
            if target is None or target >= entry:
                continue

        if risk <= 0:
            continue
        planned_rr = abs(target - entry) / risk
        if planned_rr < min_rr:
            continue

        engine.open_trade(
            time=now,
            price=entry,
            direction=direction,
            stop_loss=float(stop),
            take_profit=float(target),
        )
        traded_killzones.add((session_day, killzone))
        open_meta = {
            "entry_idx": i,
            "setup": "vwap_ema_round_retest",
            "signal_source": signal_meta["signal_source"],
            "touch_price": signal_meta["touch_price"],
            "round_level": entry_round,
            "trend_context": "bullish" if direction == "long" else "bearish",
            "planned_rr": planned_rr,
            "vwap": float(row["vwap"]),
            "ema20": float(row["ema20"]),
            "atr": float(row["atr"]),
            "killzone": killzone,
            "zone_lo": signal_meta["zone_lo"],
            "zone_hi": signal_meta["zone_hi"],
        }

    if engine.current_trade is not None and open_meta is not None:
        engine.close_trade(df.index[-1], float(df["close"].iloc[-1]), "end_of_data")
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
    backtest_result = BacktestResult(
        trades=trades,
        equity_curve=equity_series,
        initial_capital=engine.initial_capital,
        final_capital=engine.capital,
    )
    monte_carlo = backtest_result.monte_carlo_simulation(n_simulations=500)

    backtest_trades = []
    for idx, trade in enumerate(trades):
        meta = trade_meta[idx] if idx < len(trade_meta) else {}
        round_level = meta.get("round_level")
        signal_source = meta.get("signal_source", "vwap")
        backtest_trades.append(
            {
                "id": f"nas100-bounce-{idx}",
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
                "notes": f"5m {trade.direction} {signal_source} retest near round {round_level} in {meta.get('killzone', '-')}",
                "tags": [
                    "strategy:nas100_vwap_ema_bounce",
                    f"signal:{signal_source}",
                    f"round:{round_level}",
                    f"killzone:{meta.get('killzone', '-')}",
                ],
                "meta": meta,
            }
        )

    result = {
        "id": OUTPUT_NAME,
        "name": "NAS100 5m VWAP + EMA Bounce",
        "symbol": SYMBOL,
        "asset_type": ASSET_TYPE,
        "timeframe": TIMEFRAME,
        "strategy": "vwap_ema_round_retest",
        "trades": backtest_trades,
        "summary": {
            "total_trades": len(trades),
            "wins": sum(1 for trade in trades if trade.pnl is not None and trade.pnl > 0),
            "win_rate": (sum(1 for trade in trades if trade.pnl is not None and trade.pnl > 0) / len(trades) * 100) if trades else 0.0,
            "return_pct": ((engine.capital - engine.initial_capital) / engine.initial_capital * 100),
            "final_capital": engine.capital,
            "max_drawdown": backtest_result.max_drawdown,
            "profit_factor": backtest_result.profit_factor,
            "avg_rr": backtest_result.avg_rr,
        },
        "monte_carlo": monte_carlo,
        "kill_zones_utc": [f"{start:02d}:00-{end:02d}:00" for start, end in KILL_ZONES],
    }

    output_dir = Path(__file__).parents[2] / "data" / "backtests"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{OUTPUT_NAME}.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    print(json.dumps({"output": str(output_path), "summary": result["summary"]}, indent=2))
    return result


if __name__ == "__main__":
    run()
