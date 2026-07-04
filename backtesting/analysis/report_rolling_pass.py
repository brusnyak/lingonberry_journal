"""
CLI: report rolling-window prop-challenge pass rate for a strategy.

Reuses the same engine (`backtesting.engine.runner.run`) and prop rules
(`backtesting.prop.rules`) as every other backtest in this project -- this
just adds the rolling-window pass-rate question on top via
`backtesting.analysis.rolling_pass_rate`, instead of writing a fresh
one-off script per strategy.

Usage:
    python -m backtesting.analysis.report_rolling_pass --strategy orb --account 25k
    python -m backtesting.analysis.report_rolling_pass --strategy overnight --account 100k
"""
from __future__ import annotations

import argparse

from backtesting.analysis.rolling_pass_rate import rolling_window_pass_rate
from backtesting.engine.costs import ForexCosts
from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.prop.rules import GFT_25K_2STEP, GFT_100K_1STEP

STRATEGIES = {
    "orb": {
        "symbol": "NAS100", "entry_tf": "5", "htf_tf": "240",
        "costs": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=1.5),
        "module": "backtesting.lvl2_orb.orb_wide_stop", "cls": "OrbNyWideStop",
        "kwargs": {"htf_key": "240"},
    },
    "overnight": {
        "symbol": "NAS100", "entry_tf": "5", "htf_tf": "240",
        "costs": dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=1.5),
        "module": "backtesting.lvl2_overnight_drift.overnight_drift", "cls": "OvernightDrift",
        "kwargs": {"htf_key": "240"},
    },
}
ACCOUNTS = {"25k": GFT_25K_2STEP, "100k": GFT_100K_1STEP}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", choices=STRATEGIES, required=True)
    ap.add_argument("--account", choices=ACCOUNTS, required=True)
    ap.add_argument("--window-days", type=int, default=30)
    ap.add_argument("--risk-pct", type=float, default=None)
    args = ap.parse_args()

    spec = STRATEGIES[args.strategy]
    account = ACCOUNTS[args.account]
    import importlib
    mod = importlib.import_module(spec["module"])
    strat_cls = getattr(mod, spec["cls"])
    kwargs = dict(spec["kwargs"])
    if args.risk_pct is not None:
        kwargs["risk_pct"] = args.risk_pct
    strat = strat_cls(**kwargs)

    data = {spec["entry_tf"]: load_data(spec["symbol"], spec["entry_tf"])}
    if spec.get("htf_tf"):
        data[spec["htf_tf"]] = load_data(spec["symbol"], spec["htf_tf"])

    result = run(strat, data, entry_tf=spec["entry_tf"],
                 costs=ForexCosts(seed=42, **spec["costs"]), initial_equity=account.initial_equity)
    trades = result.to_df()
    print(f"{args.strategy} on {spec['symbol']}, {account.name}, full dataset: {len(trades)} trades")

    r = rolling_window_pass_rate(trades, account, window_days=args.window_days)
    print(f"Rolling {args.window_days}-day windows tested: {r.n_windows}")
    print(f"  Pass rate:   {r.pass_rate*100:.1f}%  ({r.n_passed} windows)")
    print(f"  Breach rate: {r.breach_rate*100:.1f}%  ({r.n_breached} windows)")
    print(f"  Neither:     {r.n_neither} windows")
    if r.median_days_to_pass is not None:
        print(f"  Median days-to-pass (when it passes): {r.median_days_to_pass:.0f}")


if __name__ == "__main__":
    main()
