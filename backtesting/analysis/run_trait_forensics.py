"""
Runs day-of-week and volatility-regime forensics on ORB and OvernightDrift's
CURRENT best (HTF-filtered) versions, full population, both strategies.
Reuses `engine.runner.run()` for the backtest itself -- no separate
backtest logic, only the trait-splitting is new.

Usage:
    python -m backtesting.analysis.run_trait_forensics
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.analysis.trait_forensics import day_of_week_forensics, volatility_regime_forensics
from backtesting.engine.costs import ForexCosts
from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.lvl2_orb.orb_wide_stop import OrbNyWideStop
from backtesting.lvl2_overnight_drift.overnight_drift import OvernightDrift

COSTS = dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=1.5)


def _htf_atr_series(symbol: str, tf: str, period: int = 14) -> pd.DataFrame:
    d = load_data(symbol, tf).sort_values("ts").reset_index(drop=True)
    high, low, close = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = np.full(len(close), np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return pd.DataFrame({"ts": d["ts"], "atr": atr})


def main() -> None:
    htf_atr = _htf_atr_series("NAS100", "240")

    d5 = load_data("NAS100", "5")
    d240 = load_data("NAS100", "240")

    orb_res = run(OrbNyWideStop(htf_key="240"), {"5": d5, "240": d240}, entry_tf="5",
                  costs=ForexCosts(seed=42, **COSTS), initial_equity=10_000)
    orb_trades = orb_res.to_df()
    day_of_week_forensics(orb_trades, "ORB (HTF-filtered)")
    volatility_regime_forensics(orb_trades, htf_atr, "ORB (HTF-filtered)")

    on_res = run(OvernightDrift(htf_key="240"), {"5": d5, "240": d240}, entry_tf="5",
                 costs=ForexCosts(seed=42, **COSTS), initial_equity=10_000)
    on_trades = on_res.to_df()
    day_of_week_forensics(on_trades, "OvernightDrift (HTF-filtered)")
    volatility_regime_forensics(on_trades, htf_atr, "OvernightDrift (HTF-filtered)")


if __name__ == "__main__":
    main()
