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
    in_ny_news_caution,
    in_primary_kill_zone,
    last_directional_break,
    recent_sweep_bias,
    recent_swing_bias,
    round_levels_around,
    zone_retest_bias,
)


CONFIGS = [
    {"id": "hyb_a", "killzone": "preferred", "require_sweep": False, "require_round": True, "block_news": True, "block_open_fvg": True, "min_confluence": 5},
    {"id": "hyb_b", "killzone": "strict", "require_sweep": False, "require_round": True, "block_news": True, "block_open_fvg": True, "min_confluence": 5},
    {"id": "hyb_c", "killzone": "preferred", "require_sweep": True, "require_round": True, "block_news": True, "block_open_fvg": True, "min_confluence": 5},
    {"id": "hyb_d", "killzone": "preferred", "require_sweep": False, "require_round": False, "block_news": True, "block_open_fvg": True, "min_confluence": 6},
    {"id": "hyb_e", "killzone": "strict", "require_sweep": True, "require_round": True, "block_news": True, "block_open_fvg": True, "min_confluence": 4},
    {"id": "hyb_f", "killzone": "preferred", "require_sweep": False, "require_round": True, "block_news": False, "block_open_fvg": True, "min_confluence": 6},
]


def recent_open_fvg_invalid(ms: Dict, entry_price: float, direction: str, atr: float, local_idx: int) -> bool:
    for fvg in ms.get("fvgs", []):
        if getattr(fvg, "mitigated", False):
            continue
        if fvg.index >= local_idx:
            continue
        midpoint = (fvg.top + fvg.bottom) / 2
        if direction == "long" and midpoint < entry_price and (entry_price - midpoint) <= atr * 3.0:
            return True
        if direction == "short" and midpoint > entry_price and (midpoint - entry_price) <= atr * 3.0:
            return True
    return False


def price_bias(bar: pd.Series) -> str:
    if float(bar["close"]) > float(bar["vwap"]) and float(bar["close"]) > float(bar["ema20"]):
        return "bullish"
    if float(bar["close"]) < float(bar["vwap"]) and float(bar["close"]) < float(bar["ema20"]):
        return "bearish"
    return "neutral"


def pivot_target(ms: Dict, entry_price: float, direction: str, round_levels: List[float]) -> Optional[float]:
    candidates: List[float] = []
    if direction == "long":
        candidates += [s.price for s in ms.get("swing_highs", []) if s.price > entry_price]
        candidates += [lvl.price for lvl in ms.get("liquidity_levels", []) if not lvl.swept and lvl.price > entry_price]
        candidates += [((f.top + f.bottom) / 2) for f in ms.get("fvgs", []) if f.type == "bearish" and ((f.top + f.bottom) / 2) > entry_price]
        candidates += [level for level in round_levels if level > entry_price]
        return min(candidates) if candidates else None
    candidates += [s.price for s in ms.get("swing_lows", []) if s.price < entry_price]
    candidates += [lvl.price for lvl in ms.get("liquidity_levels", []) if not lvl.swept and lvl.price < entry_price]
    candidates += [((f.top + f.bottom) / 2) for f in ms.get("fvgs", []) if f.type == "bullish" and ((f.top + f.bottom) / 2) < entry_price]
    candidates += [level for level in round_levels if level < entry_price]
    return max(candidates) if candidates else None


def pivot_stop(ms: Dict, bar: pd.Series, entry_price: float, direction: str, atr: float) -> float:
    if direction == "long":
        lows = [s.price for s in ms.get("swing_lows", []) if s.price < entry_price]
        base = max(lows) if lows else min(float(bar["low"]), float(bar["vwap"]), float(bar["ema20"]))
        return base - max(atr * 0.2, 4.0)
    highs = [s.price for s in ms.get("swing_highs", []) if s.price > entry_price]
    base = min(highs) if highs else max(float(bar["high"]), float(bar["vwap"]), float(bar["ema20"]))
    return base + max(atr * 0.2, 4.0)


def build_context(df_5m: pd.DataFrame, df_30m: pd.DataFrame, i: int) -> Optional[Dict]:
    bar = df_5m.iloc[i]
    now = df_5m.index[i]
    if pd.isna(bar["atr"]) or float(bar["atr"]) <= 0:
        return None
    if not (
        abs(float(bar["close"]) - float(bar["vwap"])) <= float(bar["atr"]) * 1.75
        or abs(float(bar["close"]) - float(bar["ema20"])) <= float(bar["atr"]) * 1.75
        or in_primary_kill_zone(now)
    ):
        return None
    window = df_5m.iloc[max(0, i - 40) : i + 1].copy()
    if len(window) < 24:
        return None
    ms = analyze_market_structure(window, swing_period=3, volume_filter=False, round_level_interval=50, premium_discount_lookback=30)
    local_idx = len(window) - 1
    nearest_round = min(round_levels_around(float(bar["close"])), key=lambda x: abs(x - float(bar["close"])))
    return {
        "time": now,
        "bar": bar,
        "ms": ms,
        "local_idx": local_idx,
        "htf_bias": htf_bias(df_30m, now),
        "local_trend": ms.get("current_trend", "neutral"),
        "swing_bias": recent_swing_bias(ms, local_idx),
        "break_label": last_directional_break(ms, local_idx),
        "sweep_bias": recent_sweep_bias(ms, local_idx),
        "retest_bias": zone_retest_bias(ms, bar, local_idx),
        "price_bias": price_bias(bar),
        "killzone": in_primary_kill_zone(now),
        "news": in_ny_news_caution(now),
        "round_level": nearest_round,
        "near_round": abs(float(bar["close"]) - nearest_round) <= max(float(bar["atr"]) * 0.5, 12.0),
    }


def decide(ctx: Dict, cfg: Dict) -> Optional[str]:
    if cfg["killzone"] == "strict" and not ctx["killzone"]:
        return None
    if cfg["block_news"] and ctx["news"]:
        return None
    if cfg["require_round"] and not ctx["near_round"]:
        return None
    if ctx["break_label"] is None:
        return None

    def bull_ok() -> bool:
        confluence = sum([
            ctx["htf_bias"] == "bullish",
            ctx["local_trend"] == "bullish",
            ctx["swing_bias"] == "bullish",
            ctx["retest_bias"] == "bullish",
            ctx["price_bias"] == "bullish",
            ctx["break_label"] in {"CHoCH:bullish", "BOS:bullish"},
            ctx["sweep_bias"] == "bullish",
            ctx["killzone"],
        ])
        if cfg["require_sweep"] and ctx["sweep_bias"] != "bullish":
            return False
        if ctx["retest_bias"] == "bearish" or ctx["price_bias"] == "bearish":
            return False
        if ctx["htf_bias"] != "bullish":
            return False
        return confluence >= cfg["min_confluence"]

    def bear_ok() -> bool:
        confluence = sum([
            ctx["htf_bias"] == "bearish",
            ctx["local_trend"] == "bearish",
            ctx["swing_bias"] == "bearish",
            ctx["retest_bias"] == "bearish",
            ctx["price_bias"] == "bearish",
            ctx["break_label"] in {"CHoCH:bearish", "BOS:bearish"},
            ctx["sweep_bias"] == "bearish",
            ctx["killzone"],
        ])
        if cfg["require_sweep"] and ctx["sweep_bias"] != "bearish":
            return False
        if ctx["retest_bias"] == "bullish" or ctx["price_bias"] == "bullish":
            return False
        if ctx["htf_bias"] != "bearish":
            return False
        return confluence >= cfg["min_confluence"]

    if bull_ok():
        return "long"
    if bear_ok():
        return "short"
    return None


def run_one(df_5m: pd.DataFrame, df_30m: pd.DataFrame, cfg: Dict) -> Dict:
    engine = BacktestEngine(initial_capital=20000.0, commission=0.0, slippage=0.0, risk_per_trade=0.01, position_sizing="risk_pct")
    trade_meta: List[Dict] = []
    open_meta: Optional[Dict] = None
    prev_closed_count = 0
    cooldown_until = -1

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
        direction = decide(ctx, cfg)
        if direction is None:
            continue
        if cfg["block_open_fvg"] and recent_open_fvg_invalid(ctx["ms"], float(ctx["bar"]["close"]), direction, float(ctx["bar"]["atr"]), ctx["local_idx"]):
            continue

        entry = float(ctx["bar"]["close"])
        target = pivot_target(ctx["ms"], entry, direction, round_levels_around(entry))
        stop = pivot_stop(ctx["ms"], ctx["bar"], entry, direction, float(ctx["bar"]["atr"]))
        if target is None:
            target = entry + (float(ctx["bar"]["atr"]) * 2.0 if direction == "long" else -float(ctx["bar"]["atr"]) * 2.0)
        risk = (entry - stop) if direction == "long" else (stop - entry)
        reward = (target - entry) if direction == "long" else (entry - target)
        if risk <= 0 or reward <= 0 or reward / risk < 1.0:
            continue

        engine.open_trade(ctx["time"], entry, direction=direction, stop_loss=float(stop), take_profit=float(target))
        open_meta = {
            "entry_idx": i,
            "config": cfg["id"],
            "htf_bias": ctx["htf_bias"],
            "local_trend": ctx["local_trend"],
            "swing_bias": ctx["swing_bias"],
            "break_label": ctx["break_label"],
            "sweep_bias": ctx["sweep_bias"],
            "retest_bias": ctx["retest_bias"],
            "killzone": ctx["killzone"],
            "news": ctx["news"],
            "round_level": ctx["round_level"],
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
            "id": f"{cfg['id']}-{idx}",
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
            "notes": f"{cfg['id']} {trade.direction}",
            "tags": [f"strategy:{cfg['id']}"],
            "meta": meta,
        })

    return {
        "id": cfg["id"],
        "name": cfg["id"],
        "symbol": SYMBOL,
        "asset_type": ASSET_TYPE,
        "timeframe": TIMEFRAME,
        "strategy": cfg["id"],
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
    }


def run(limit_5m: int = 2500, limit_30m: int = 1500) -> Dict:
    loader = DataLoader()
    df_5m = add_ema_atr(add_session_vwap(loader.load(SYMBOL, TIMEFRAME, limit=limit_5m, prefer_parquet=True).copy()))
    df_30m = add_ema_atr(add_session_vwap(loader.load(SYMBOL, HTF_TIMEFRAME, limit=limit_30m, prefer_parquet=True).copy()))

    results = []
    backtests_dir = Path(__file__).parents[2] / "data" / "backtests"
    backtests_dir.mkdir(parents=True, exist_ok=True)
    for cfg in CONFIGS:
        result = run_one(df_5m, df_30m, cfg)
        results.append({"id": result["id"], **result["summary"]})
        (backtests_dir / f"nas100_{cfg['id']}.json").write_text(json.dumps(result, indent=2))

    # rank by win rate first, then trade count, then return
    ranked = sorted(results, key=lambda x: (x["win_rate"], min(x["total_trades"], 30), x["return_pct"]), reverse=True)
    payload = {"symbol": SYMBOL, "timeframe": TIMEFRAME, "results": ranked}
    analysis_dir = Path(__file__).parents[2] / "data" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    (analysis_dir / "nas100_hybrid_tuning.json").write_text(json.dumps(payload, indent=2))
    lines = ["# NAS100 Hybrid Tuning", ""]
    for item in ranked:
        lines.append(f"- `{item['id']}` trades={item['total_trades']} wr={item['win_rate']:.2f}% ret={item['return_pct']:.2f}% pf={item['profit_factor']:.2f} dd={item['max_drawdown']:.2f}%")
    (analysis_dir / "nas100_hybrid_tuning.md").write_text("\n".join(lines))
    print(json.dumps(payload, indent=2))
    return payload


if __name__ == "__main__":
    run()
