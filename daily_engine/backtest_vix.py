"""Lvl 2 — falsify (or confirm) the AUDUSD VIX-level mean-reversion signal.

Signal (causal, mean-reversion): hold AUDUSD LONG while fear is elevated, i.e.
VIX above its own trailing median. The lvl-1.5 scan showed corr(VIX_level,
forward return) is positive and sign-stable across both halves on AUDUSD.

This evaluates it as a daily position (not discrete trades): the cleanest way
to get an honest equity curve + max DD. Position changes pay a round-trip cost.
Kill criterion: net-of-cost return must be POSITIVE and SAME-SIGN in both
halves. If it only works in one half, or dies after cost, it's a regime artifact.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from daily_engine.data import build_dataset

# AUDUSD ~0.65; 1 pip = 0.0001 ≈ 1.5 bps/side. Conservative round-trip = 3 bps.
COST_RT = 0.0003
VIX_WIN = 252  # trailing window for the median threshold (causal)


def _stats(daily_ret: pd.Series, pos: pd.Series) -> dict:
    eq = (1 + daily_ret).cumprod()
    dd = (eq / eq.cummax() - 1.0).min()
    n_yr = len(daily_ret) / 252
    cagr = eq.iloc[-1] ** (1 / n_yr) - 1 if n_yr > 0 and eq.iloc[-1] > 0 else float("nan")
    sharpe = daily_ret.mean() / daily_ret.std() * np.sqrt(252) if daily_ret.std() > 0 else 0.0
    return dict(
        total=round(eq.iloc[-1] - 1, 4), cagr=round(cagr, 4),
        maxDD=round(dd, 4), sharpe=round(sharpe, 2),
        time_in=round((pos != 0).mean(), 3),
        ret_DD=round(cagr / abs(dd), 2) if dd != 0 else float("nan"),
    )


def run(symbol: str = "AUDUSD", mode: str = "long", cost: float = COST_RT) -> None:
    ds = build_dataset(symbol)
    fwd = ds["close"].shift(-1) / ds["close"] - 1.0  # next-day return

    vix = ds["vix"]
    thresh = vix.rolling(VIX_WIN, min_periods=60).median()
    elevated = (vix > thresh)

    if mode == "long":      # long only when fear elevated, else flat
        pos = elevated.astype(float)
    else:                   # long elevated / short calm
        pos = elevated.astype(float) * 2 - 1

    pos = pos.fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.abs())
    strat = pos * fwd - turnover * cost
    strat = strat.dropna()
    pos = pos.loc[strat.index]

    mid = len(strat) // 2
    print(f"\n=== {symbol}  VIX mean-reversion  mode={mode}  cost={cost*1e4:.0f}bps RT ===")
    print(f"period {ds.index.min().date()} -> {ds.index.max().date()}   trades/yr≈{turnover.sum()/ (len(strat)/252):.0f}")
    print(f"FULL  {_stats(strat, pos)}")
    print(f"EARLY {_stats(strat.iloc[:mid], pos.iloc[:mid])}")
    print(f"LATE  {_stats(strat.iloc[mid:], pos.iloc[mid:])}")

    # baselines
    bh = fwd.loc[strat.index]
    print(f"B&H   {_stats(bh, pd.Series(1.0, index=bh.index))}  (always-long {symbol})")


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "AUDUSD"
    run(sym, "long")
    run(sym, "longshort")
