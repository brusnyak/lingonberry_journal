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

import pandas as pd

from backtesting.crypto.data import load_crypto, load_market_specs
from backtesting.crypto.mtf_cascade_direction import DEFAULT_SYMBOLS
from backtesting.crypto.strategies.mtf_cascade_foundation import MtfCascadeFoundation
from backtesting.engine.costs import CryptoCosts
from backtesting.engine.runner import run
from backtesting.prop.rules import CRYPTO_50, CRYPTO_300, PropAccount
from backtesting.analysis.rolling_return_stats import rolling_window_return_stats


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
    costs = CryptoCosts(
        leverage=leverage,
        min_notional=specs.get("min_notional", 0.0),
        min_qty=specs.get("min_qty", 0.0),
        qty_step=specs.get("qty_step", 0.0),
        tick_size=specs.get("tick_size", 0.0),
    )
    strat = MtfCascadeFoundation(risk_pct=risk_pct, min_rr=min_rr, horizon_bars=horizon_bars)
    result = run(strat, data, entry_tf="5", costs=costs, initial_equity=initial_equity)

    rep = result.report
    return {
        "symbol": symbol,
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
        "_trades_df": result.to_df(),
    }


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
    args = parser.parse_args()

    account: PropAccount = CRYPTO_300 if args.account == "CRYPTO_300" else CRYPTO_50

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    rows = []
    for symbol in symbols:
        r = run_foundation_backtest(
            symbol, days=args.days, exchange=args.exchange, risk_pct=args.risk_pct,
            min_rr=args.min_rr, horizon_bars=args.horizon, initial_equity=account.initial_equity,
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
