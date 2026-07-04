"""
Reusable per-trait forensics: splits a trades DataFrame by day-of-week and
by volatility regime (ATR percentile at entry), reporting PF/WR/avg-pnl per
bucket on the FULL trade population -- same discipline as
lvl2_orb/trade_forensics.py (avoid the cherry-picked-sample trap), but
generic across strategies instead of one script per strategy.

Day-of-week is literature-motivated for the overnight-drift mechanism
specifically ("Weekly Seasonality in Overnight Effects of the Stock
Market" -- found during the intraday-momentum/overnight-drift research
round, not yet checked). Volatility regime is motivated by Zarattini's own
ORB methodology (filtering for "stocks in play" / abnormal activity).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _pf(sub: pd.DataFrame) -> float:
    w, l = sub[sub.pnl > 0], sub[sub.pnl <= 0]
    if len(l) == 0 or l.pnl.sum() == 0:
        return float("inf") if len(w) else 0.0
    return w.pnl.sum() / abs(l.pnl.sum())


def day_of_week_forensics(trades: pd.DataFrame, label: str = "") -> None:
    tr = trades.copy()
    tr["entry_time"] = pd.to_datetime(tr["entry_time"])
    tr["dow"] = tr["entry_time"].dt.day_name()
    print(f"\n--- {label} day-of-week (entry day, full population n={len(tr)}) ---")
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for d in order:
        sub = tr[tr["dow"] == d]
        if len(sub) == 0:
            continue
        print(f"  {d:<10} n={len(sub):>4}  wr={100*(sub.pnl>0).mean():>5.1f}%  "
              f"avg_pnl=${sub.pnl.mean():>7.2f}  PF={_pf(sub):.2f}")


def volatility_regime_forensics(trades: pd.DataFrame, atr_series: pd.DataFrame, label: str = "") -> None:
    """
    atr_series: DataFrame with ['ts', 'atr'] columns (any timeframe -- e.g.
    the HTF series a strategy already uses for its trend filter), matched
    to each trade's entry_time by nearest-prior timestamp. Decoupled from
    any strategy's internal bar-index bookkeeping -- just needs a plain
    ATR time series, reusable across strategies.
    """
    atr_series = atr_series.sort_values("ts").reset_index(drop=True)
    atr_ts = pd.to_datetime(atr_series["ts"]).to_numpy()
    atr_vals = atr_series["atr"].to_numpy()

    tr = trades.copy()
    tr["entry_time"] = pd.to_datetime(tr["entry_time"])
    entry_ts = tr["entry_time"].to_numpy()
    idx = np.searchsorted(atr_ts, entry_ts, side="right") - 1
    valid_mask = idx >= 0
    atr_at_entry = np.full(len(tr), np.nan)
    atr_at_entry[valid_mask] = atr_vals[idx[valid_mask]]

    pctile = pd.Series(atr_at_entry).rank(pct=True)
    tr["atr_pctile"] = pctile.to_numpy()
    print(f"\n--- {label} volatility regime (ATR percentile at entry, n={int(valid_mask.sum())}) ---")
    for lo, hi, name in [(0.0, 0.33, "low vol (bottom third)"),
                         (0.33, 0.67, "mid vol"),
                         (0.67, 1.01, "high vol (top third)")]:
        sub = tr[(tr["atr_pctile"] >= lo) & (tr["atr_pctile"] < hi)]
        if len(sub) == 0:
            continue
        print(f"  {name:<24} n={len(sub):>4}  wr={100*(sub.pnl>0).mean():>5.1f}%  "
              f"avg_pnl=${sub.pnl.mean():>7.2f}  PF={_pf(sub):.2f}")
