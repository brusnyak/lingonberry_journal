import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest.engine import BacktestEngine, BacktestResult
from src.data.loader import DataLoader

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
    in_primary_kill_zone,
    last_directional_break,
    recent_sweep_bias,
    recent_swing_bias,
    round_levels_around,
    zone_retest_bias,
)
from src.features.market_structure import analyze_market_structure


VARIANTS = [
    {
        "id": "strict_reversal",
        "name": "Strict Reversal Template",
        "require_killzone": True,
        "allow_outside": False,
        "require_retest": True,
        "require_sweep": True,
        "allowed_breaks": {"CHoCH:bullish", "CHoCH:bearish", "BOS:bullish", "BOS:bearish"},
        "continuation": False,
    },
    {
        "id": "strict_continuation",
        "name": "Strict Continuation Template",
        "require_killzone": True,
        "allow_outside": False,
        "require_retest": True,
        "require_sweep": False,
        "allowed_breaks": {"BOS:bullish", "BOS:bearish"},
        "continuation": True,
    },
    {
        "id": "hybrid_kz_preferred",
        "name": "Hybrid Kill Zone Preferred",
        "require_killzone": False,
        "allow_outside": True,
        "require_retest": True,
        "require_sweep": False,
        "allowed_breaks": {"CHoCH:bullish", "CHoCH:bearish", "BOS:bullish", "BOS:bearish"},
        "continuation": "hybrid",
    },
    {
        "id": "sweep_then_retest",
        "name": "Sweep Then Retest",
        "require_killzone": False,
        "allow_outside": True,
        "require_retest": True,
        "require_sweep": True,
        "allowed_breaks": {"CHoCH:bullish", "CHoCH:bearish"},
        "continuation": False,
    },
]


def build_context(df_5m: pd.DataFrame, df_30m: pd.DataFrame, i: int) -> Optional[Dict]:
    now = df_5m.index[i]
    bar = df_5m.iloc[i]
    if pd.isna(bar["atr"]) or float(bar["atr"]) <= 0:
        return None
    if not (
        abs(float(bar["close"]) - float(bar["vwap"])) <= float(bar["atr"]) * 1.5
        or abs(float(bar["close"]) - float(bar["ema20"])) <= float(bar["atr"]) * 1.5
        or in_primary_kill_zone(now)
    ):
        return None

    window = df_5m.iloc[max(0, i - 36) : i + 1].copy()
    if len(window) < 24:
        return None
    ms = analyze_market_structure(window, swing_period=3, volume_filter=False, round_level_interval=50, premium_discount_lookback=30)
    local_idx = len(window) - 1
    higher_tf = htf_bias(df_30m, now)
    local_trend = ms.get("current_trend", "neutral")
    swing_bias = recent_swing_bias(ms, local_idx)
    break_label = last_directional_break(ms, local_idx)
    sweep_bias = recent_sweep_bias(ms, local_idx)
    retest_bias = zone_retest_bias(ms, bar, local_idx)
    price_bias = "bullish" if float(bar["close"]) > float(bar["vwap"]) and float(bar["close"]) > float(bar["ema20"]) else "bearish" if float(bar["close"]) < float(bar["vwap"]) and float(bar["close"]) < float(bar["ema20"]) else "neutral"
    round_levels = round_levels_around(float(bar["close"]))
    nearest_round = min(round_levels, key=lambda x: abs(x - float(bar["close"])))
    near_round = abs(float(bar["close"]) - nearest_round) <= max(float(bar["atr"]) * 0.5, 12.0)
    return {
        "time": now,
        "bar": bar,
        "ms": ms,
        "htf_bias": higher_tf,
        "local_trend": local_trend,
        "swing_bias": swing_bias,
        "break_label": break_label,
        "sweep_bias": sweep_bias,
        "retest_bias": retest_bias,
        "price_bias": price_bias,
        "killzone": in_primary_kill_zone(now),
        "news_caution": in_ny_news_caution(now),
        "round_levels": round_levels,
        "nearest_round": nearest_round,
        "near_round": near_round,
    }


def decide_direction(ctx: Dict, variant: Dict) -> Optional[str]:
    if variant["require_killzone"] and not ctx["killzone"]:
        return None
    if ctx["news_caution"]:
        return None
    if not variant["allow_outside"] and not ctx["killzone"]:
        return None
    if variant["require_retest"] and ctx["retest_bias"] == "neutral":
        return None
    if variant["require_sweep"] and ctx["sweep_bias"] == "neutral":
        return None
    if ctx["break_label"] not in variant["allowed_breaks"]:
        return None
    if not ctx["near_round"]:
        return None

    if variant["continuation"] is True:
        if (
            ctx["htf_bias"] == "bullish"
            and ctx["local_trend"] == "bullish"
            and ctx["swing_bias"] == "bullish"
            and ctx["price_bias"] == "bullish"
            and ctx["break_label"] == "BOS:bullish"
            and ctx["retest_bias"] == "bullish"
        ):
            return "long"
        if (
            ctx["htf_bias"] == "bearish"
            and ctx["local_trend"] == "bearish"
            and ctx["swing_bias"] == "bearish"
            and ctx["price_bias"] == "bearish"
            and ctx["break_label"] == "BOS:bearish"
            and ctx["retest_bias"] == "bearish"
        ):
            return "short"
        return None

    if variant["continuation"] == "hybrid":
        if (
            ctx["htf_bias"] == "bullish"
            and ctx["price_bias"] == "bullish"
            and ctx["retest_bias"] == "bullish"
            and ctx["break_label"] in {"CHoCH:bullish", "BOS:bullish"}
            and ctx["local_trend"] == "bullish"
        ):
            return "long"
        if (
            ctx["htf_bias"] == "bearish"
            and ctx["price_bias"] == "bearish"
            and ctx["retest_bias"] == "bearish"
            and ctx["break_label"] in {"CHoCH:bearish", "BOS:bearish"}
            and ctx["local_trend"] == "bearish"
        ):
            return "short"
        return None

    if (
        ctx["htf_bias"] == "bullish"
        and ctx["price_bias"] == "bullish"
        and ctx["retest_bias"] == "bullish"
        and ctx["break_label"] in {"CHoCH:bullish", "BOS:bullish"}
        and (ctx["sweep_bias"] == "bullish" or not variant["require_sweep"])
    ):
        return "long"
    if (
        ctx["htf_bias"] == "bearish"
        and ctx["price_bias"] == "bearish"
        and ctx["retest_bias"] == "bearish"
        and ctx["break_label"] in {"CHoCH:bearish", "BOS:bearish"}
        and (ctx["sweep_bias"] == "bearish" or not variant["require_sweep"])
    ):
        return "short"
    return None


def run_single_variant(df_5m: pd.DataFrame, df_30m: pd.DataFrame, variant: Dict) -> Dict:
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

        ctx = build_context(df_5m, df_30m, i)
        if ctx is None:
            continue
        direction = decide_direction(ctx, variant)
        if direction is None:
            continue

        bar = ctx["bar"]
        entry = float(bar["close"])
        target = find_target_from_structure(ctx["ms"], entry, direction, ctx["round_levels"])
        stop = find_stop_from_structure(ctx["ms"], bar, entry, direction, float(bar["atr"]))
        if target is None:
            target = entry + (float(bar["atr"]) * 2.0 if direction == "long" else -float(bar["atr"]) * 2.0)

        risk = (entry - stop) if direction == "long" else (stop - entry)
        reward = (target - entry) if direction == "long" else (entry - target)
        if risk <= 0 or reward <= 0 or reward / risk < 1.0:
            continue

        engine.open_trade(ctx["time"], entry, direction=direction, stop_loss=float(stop), take_profit=float(target))
        open_meta = {
            "entry_idx": i,
            "variant": variant["id"],
            "htf_bias": ctx["htf_bias"],
            "local_trend": ctx["local_trend"],
            "swing_bias": ctx["swing_bias"],
            "break_label": ctx["break_label"],
            "sweep_bias": ctx["sweep_bias"],
            "retest_bias": ctx["retest_bias"],
            "killzone": ctx["killzone"],
            "round_level": ctx["nearest_round"],
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
            "id": f"{variant['id']}-{idx}",
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
            "notes": f"{variant['name']} {trade.direction}",
            "tags": [f"strategy:{variant['id']}"],
            "meta": meta,
        })

    return {
        "id": variant["id"],
        "name": variant["name"],
        "symbol": SYMBOL,
        "asset_type": ASSET_TYPE,
        "timeframe": TIMEFRAME,
        "strategy": variant["id"],
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
        "monte_carlo": result_obj.monte_carlo_simulation(n_simulations=300),
    }


def run(limit_5m: int = 2500, limit_30m: int = 1500) -> Dict:
    loader = DataLoader()
    df_5m = add_ema_atr(add_session_vwap(loader.load(SYMBOL, TIMEFRAME, limit=limit_5m, prefer_parquet=True).copy()))
    df_30m = add_ema_atr(add_session_vwap(loader.load(SYMBOL, HTF_TIMEFRAME, limit=limit_30m, prefer_parquet=True).copy()))

    results = []
    output_dir = Path(__file__).parents[2] / "data" / "backtests"
    output_dir.mkdir(parents=True, exist_ok=True)
    for variant in VARIANTS:
        result = run_single_variant(df_5m, df_30m, variant)
        results.append({"id": result["id"], "name": result["name"], **result["summary"]})
        (output_dir / f"nas100_{variant['id']}.json").write_text(json.dumps(result, indent=2))

    summary = {
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "variants": results,
    }
    analysis_dir = Path(__file__).parents[2] / "data" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    (analysis_dir / "nas100_variant_summary.json").write_text(json.dumps(summary, indent=2))
    lines = ["# NAS100 Variant Summary", ""]
    for item in results:
        lines.append(f"- `{item['id']}` `{item['name']}` trades={item['total_trades']} win_rate={item['win_rate']:.2f}% return={item['return_pct']:.2f}% pf={item['profit_factor']:.2f} dd={item['max_drawdown']:.2f}%")
    (analysis_dir / "nas100_variant_summary.md").write_text("\n".join(lines))
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run()
