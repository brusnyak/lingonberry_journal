"""Proper (cost-modeled, equity-curve) backtest of the MTF cascade foundation.

Everything up to Phase 27 measured the foundation as frictionless R-multiples
(null-test harness in mtf_cascade_direction.py) -- deliberately, to isolate
signal quality from position sizing/costs. This runs the same foundation
(MtfCascadeFoundation, backtesting/crypto/strategies/mtf_cascade_foundation.py)
through the real engine: engine.runner.run() with CryptoCosts (fees, funding,
leverage, liquidation) and real per-symbol exchange specs, to get the numbers
that actually matter for a deployment decision -- trades, win rate, profit
factor, max drawdown, return, and the rolling-window DD/return distribution
(same tool used for forex: backtesting.analysis.rolling_return_stats).

Uses backtesting.crypto.data.load_crypto (source="merged" by default) for
full multi-year history -- NOT backtesting.crypto.batch's _run_one_crypto,
which calls engine.data.load_data without crypto_source and silently falls
back to the shallow ~90-120 day exchange-scoped window (the Phase 12/13 bug
this project already fixed once; do not reintroduce it by going through the
other loader).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto, load_market_specs
from backtesting.crypto.mtf_cascade_direction import DEFAULT_SYMBOLS
from backtesting.crypto.strategies.mtf_cascade_foundation import MtfCascadeFoundation
from backtesting.engine.costs import CryptoCosts, WorstCaseCryptoCosts
from backtesting.engine.runner import run
from backtesting.prop.rules import CRYPTO_50, CRYPTO_300, PropAccount
from backtesting.analysis.rolling_return_stats import rolling_window_return_stats


@dataclass(frozen=True)
class CostScenario:
    name: str
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    adverse_round_trip_pct: float = 0.0


DEFAULT_COST_SCENARIOS = [
    CostScenario("zero_fee", maker_fee=0.0, taker_fee=0.0),
    CostScenario("base_fee", maker_fee=0.0002, taker_fee=0.0004),
    CostScenario("taker_taker_fee", maker_fee=0.0004, taker_fee=0.0004),
    CostScenario("stress_20bps", adverse_round_trip_pct=0.002),
    CostScenario("stress_30bps", adverse_round_trip_pct=0.003),
    CostScenario("awful_200bps", adverse_round_trip_pct=0.02),
]


def run_foundation_backtest(
    symbol: str,
    *,
    days: int = 400,
    exchange: str = "binance",
    source: str = "merged",
    risk_pct: float = 0.005,
    min_rr: float = 1.5,
    horizon_bars: int = 200,
    leverage: float = 50.0,
    initial_equity: float = 300.0,
    cost_scenario: CostScenario | None = None,
    next_bar_fill: bool = False,
) -> dict:
    """One symbol, full pipeline: load -> run through the real engine -> report.
    Returns the engine's report dict plus the trades DataFrame for rolling-window
    analysis, or an 'error' key if data was unavailable."""
    data = {
        tf: load_crypto(symbol, tf=tf, days=days, exchange=exchange, source=source).reset_index(drop=True)
        for tf in ("240", "30", "5")
    }
    if any(df.empty for df in data.values()):
        return {"symbol": symbol, "error": "no data"}

    specs = load_market_specs(symbol, exchange)
    scenario = cost_scenario or CostScenario("base_fee")
    costs = _cost_model(scenario, specs, leverage)
    strat = MtfCascadeFoundation(risk_pct=risk_pct, min_rr=min_rr, horizon_bars=horizon_bars)
    result = run(
        strat,
        data,
        entry_tf="5",
        costs=costs,
        initial_equity=initial_equity,
        next_bar_fill=next_bar_fill,
    )

    rep = result.report
    trades_df = result.to_df()
    return {
        "symbol": symbol,
        "cost_scenario": scenario.name,
        "trades": rep.get("trades", 0),
        "win_rate": rep.get("win_rate", 0.0),
        "profit_factor": rep.get("profit_factor", 0.0),
        "payoff_ratio": rep.get("payoff_ratio", 0.0),
        "avg_r": rep.get("avg_r", 0.0),
        "return_pct": rep.get("return_pct", 0.0),
        "max_drawdown_pct": rep.get("max_drawdown_pct", 0.0),
        "sharpe": rep.get("sharpe", 0.0),
        "avg_duration_min": rep.get("avg_duration_min", 0.0),
        "error": None,
        **trade_diagnostics(trades_df),
        "_trades_df": trades_df,
    }


def run_cost_fragility_audit(
    symbol: str,
    *,
    scenarios: list[CostScenario] | None = None,
    **kwargs,
) -> pd.DataFrame:
    rows = []
    for scenario in scenarios or DEFAULT_COST_SCENARIOS:
        result = run_foundation_backtest(symbol, cost_scenario=scenario, **kwargs)
        result.pop("_trades_df", None)
        rows.append(result)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    zero = out[out["cost_scenario"] == "zero_fee"]
    if not zero.empty and "avg_r" in out:
        zero_avg_r = float(zero.iloc[0]["avg_r"])
        out["cost_drag_avg_r"] = zero_avg_r - pd.to_numeric(out["avg_r"], errors="coerce")
    return out


def trade_diagnostics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "median_stop_pct": np.nan,
            "p10_stop_pct": np.nan,
            "p90_stop_pct": np.nan,
            "sub_10bps_stop_rate": np.nan,
            "sl_rate": np.nan,
            "tp_rate": np.nan,
            "signal_exit_rate": np.nan,
            "eod_exit_rate": np.nan,
        }
    stop_pct = (trades["entry_price"].astype(float) - trades["sl"].astype(float)).abs() / trades["entry_price"].astype(float) * 100.0
    exits = trades["exit_reason"].astype(str)
    return {
        "median_stop_pct": float(stop_pct.median()),
        "p10_stop_pct": float(stop_pct.quantile(0.10)),
        "p90_stop_pct": float(stop_pct.quantile(0.90)),
        "sub_10bps_stop_rate": float((stop_pct < 0.1).mean()),
        "sl_rate": float((exits == "sl").mean()),
        "tp_rate": float((exits == "tp1").mean()),
        "signal_exit_rate": float((exits == "signal").mean()),
        "eod_exit_rate": float((exits == "eod").mean()),
    }


def _cost_model(scenario: CostScenario, specs: dict, leverage: float) -> CryptoCosts:
    cls = WorstCaseCryptoCosts if scenario.adverse_round_trip_pct > 0 else CryptoCosts
    kwargs = {
        "maker_fee": scenario.maker_fee,
        "taker_fee": scenario.taker_fee,
        "leverage": leverage,
        "min_notional": specs.get("min_notional", 0.0),
        "min_qty": specs.get("min_qty", 0.0),
        "qty_step": specs.get("qty_step", 0.0),
        "tick_size": specs.get("tick_size", 0.0),
    }
    if cls is WorstCaseCryptoCosts:
        kwargs["round_trip_pct"] = scenario.adverse_round_trip_pct
    return cls(**kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Proper cost-modeled backtest of the MTF cascade foundation, all pairs.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=400)
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--risk-pct", type=float, default=0.005)
    parser.add_argument("--min-rr", type=float, default=1.5)
    parser.add_argument("--horizon", type=int, default=200)
    parser.add_argument("--account", default="CRYPTO_300", choices=["CRYPTO_300", "CRYPTO_50"])
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--output", default="")
    parser.add_argument("--cost-audit", action="store_true", help="Run zero/base/stress/awful cost scenarios per symbol.")
    parser.add_argument("--next-bar-fill", action="store_true", help="Decide on close[i], fill at open[i+1].")
    args = parser.parse_args()

    account: PropAccount = CRYPTO_300 if args.account == "CRYPTO_300" else CRYPTO_50

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    rows = []
    for symbol in symbols:
        if args.cost_audit:
            audit = run_cost_fragility_audit(
                symbol,
                days=args.days,
                exchange=args.exchange,
                risk_pct=args.risk_pct,
                min_rr=args.min_rr,
                horizon_bars=args.horizon,
                initial_equity=account.initial_equity,
                next_bar_fill=args.next_bar_fill,
            )
            rows.extend(audit.to_dict("records"))
            continue
        r = run_foundation_backtest(
            symbol, days=args.days, exchange=args.exchange, risk_pct=args.risk_pct,
            min_rr=args.min_rr, horizon_bars=args.horizon, initial_equity=account.initial_equity,
            next_bar_fill=args.next_bar_fill,
        )
        trades_df = r.pop("_trades_df", pd.DataFrame())
        if r.get("error"):
            rows.append(r)
            continue
        roll = rolling_window_return_stats(trades_df, account, window_days=args.window_days)
        rows.append({
            **r,
            "roll_median_return_pct": roll.median_return_pct,
            "roll_worst_return_pct": roll.worst_return_pct,
            "roll_median_dd_pct": roll.median_max_dd_pct,
            "roll_worst_dd_pct": roll.worst_max_dd_pct,
            "roll_breach_rate": roll.breach_rate,
            "roll_n_windows": roll.n_windows,
        })

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    if args.output:
        df.to_csv(args.output, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
