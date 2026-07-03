"""
Trade forensics on ORB variant 2's own backtested trades -- not aggregate
stats, but per-trade context: HTF trend alignment and pre-breakout
liquidity-sweep behavior. Checked across the FULL trade population, not a
handful of examples -- the project already fell into the cherry-picked-
sample trap once this session (CLEAN.md §12, "reject entries at 30-bar
swing extremes" looked compelling on 5 examples, reversed on the full set).

Two factors tested, both grounded in why they're plausible mechanisms (not
p-hacked from a metric dump):
  1. HTF trend alignment -- does the breakout direction agree with the
     4h EMA50 slope? Standard, literature-supported ORB filter (see
     CLEAN.md #15 web research).
  2. Pre-breakout liquidity sweep -- did price sweep the prior day's
     high/low in the 2h before the opening range formed? A sweep-then-
     reverse-into-range pattern is a commonly cited reason ORB breakouts
     either have "fuel" (stops already run) or get faded (no fresh stops
     left to fund the move).

NOTE: volume confirmation (also literature-supported) is NOT tested here --
NAS100 5m data's volume column is a placeholder (constant 5.0 every bar,
verified before running this), not real tick volume. Would need better
data first.

Usage:
    python backtesting/lvl2_orb/trade_forensics.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.engine.costs import ForexCosts
from backtesting.lvl2_orb.orb_wide_stop import OrbNyWideStop

COSTS = dict(pip_size=1.0, pip_value_per_lot=1.0, fixed_spread_pips=1.5)


def _ema(close: np.ndarray, period: int) -> np.ndarray:
    alpha = 2 / (period + 1)
    out = np.full(len(close), np.nan)
    out[period - 1] = close[:period].mean()
    for i in range(period, len(close)):
        out[i] = alpha * close[i] + (1 - alpha) * out[i - 1]
    return out


def _prior_day_high_low(ts: pd.Series, high: np.ndarray, low: np.ndarray):
    dates = ts.dt.date.to_numpy()
    df = pd.DataFrame({"date": dates, "high": high, "low": low})
    daily = df.groupby("date").agg(day_high=("high", "max"), day_low=("low", "min")).shift(1)
    mapped = pd.DataFrame({"date": dates}).merge(daily, on="date", how="left")
    return mapped["day_high"].to_numpy(), mapped["day_low"].to_numpy()


def main() -> None:
    d5_full = load_data("NAS100", "5")
    d240_full = load_data("NAS100", "240")

    strat = OrbNyWideStop()
    res = run(strat, {"5": d5_full}, entry_tf="5",
              costs=ForexCosts(seed=42, **COSTS), initial_equity=10_000)
    tr = res.to_df()
    print(f"n trades = {len(tr)}")

    # HTF trend: 4h EMA50 slope, sampled at each trade's entry time
    d240 = d240_full.sort_values("ts").reset_index(drop=True)
    ema50 = _ema(d240["close"].to_numpy(), 50)
    ema_slope_up = np.concatenate([[False], np.diff(ema50) > 0])
    htf_ts = pd.to_datetime(d240["ts"], utc=True).dt.tz_localize(None).to_numpy()

    # Prior-day high/low sweep on the 5m series (2h pre-breakout window)
    d5 = d5_full.sort_values("ts").reset_index(drop=True)
    d5_ts = pd.to_datetime(d5["ts"], utc=True).dt.tz_localize(None)
    pdh, pdl = _prior_day_high_low(d5_ts, d5["high"].to_numpy(), d5["low"].to_numpy())
    d5_ts_np = d5_ts.to_numpy()

    trend_aligned, sweep_before = [], []
    for _, t in tr.iterrows():
        et = pd.Timestamp(t["entry_time"])
        if et.tzinfo is None:
            et = et.tz_localize("UTC")
        else:
            et = et.tz_convert("UTC")
        entry_time = np.datetime64(et.tz_localize(None))
        htf_idx = np.searchsorted(htf_ts, entry_time, side="right") - 1
        htf_up = ema_slope_up[htf_idx] if 0 <= htf_idx < len(ema_slope_up) else None
        is_long = "long" in t["label"]
        aligned = (htf_up == is_long) if htf_up is not None and not (isinstance(htf_up, float) and np.isnan(htf_up)) else None
        trend_aligned.append(aligned)

        i5 = np.searchsorted(d5_ts_np, entry_time, side="right") - 1
        lookback_start = max(0, i5 - 24)  # 24 * 5min = 2h
        window_hi = d5["high"].to_numpy()[lookback_start:i5]
        window_lo = d5["low"].to_numpy()[lookback_start:i5]
        pdh_i, pdl_i = pdh[i5] if i5 < len(pdh) else np.nan, pdl[i5] if i5 < len(pdl) else np.nan
        swept = bool(len(window_hi) and not np.isnan(pdh_i) and
                     ((window_hi.max() >= pdh_i) or (window_lo.min() <= pdl_i)))
        sweep_before.append(swept)

    tr = tr.assign(trend_aligned=trend_aligned, sweep_before=sweep_before)

    def group_stats(mask, label):
        sub = tr[mask]
        if len(sub) == 0:
            print(f"  {label}: n=0")
            return
        w, l = sub[sub.pnl > 0], sub[sub.pnl <= 0]
        pf = w.pnl.sum() / abs(l.pnl.sum()) if len(l) and l.pnl.sum() != 0 else float("inf")
        print(f"  {label}: n={len(sub):>4}  wr={100*(sub.pnl>0).mean():>5.1f}%  "
              f"avg_pnl=${sub.pnl.mean():>7.2f}  PF={pf:.2f}")

    print("\n--- HTF (4h EMA50 slope) trend alignment ---")
    group_stats(tr["trend_aligned"] == True, "aligned with HTF trend")
    group_stats(tr["trend_aligned"] == False, "against HTF trend")

    print("\n--- Prior-day high/low swept in the 2h before the opening range ---")
    group_stats(tr["sweep_before"] == True, "sweep occurred before breakout")
    group_stats(tr["sweep_before"] == False, "no sweep before breakout")

    print("\n--- Combined ---")
    group_stats((tr["trend_aligned"] == True) & (tr["sweep_before"] == True), "aligned + swept")
    group_stats((tr["trend_aligned"] == True) & (tr["sweep_before"] == False), "aligned + no sweep")
    group_stats((tr["trend_aligned"] == False) & (tr["sweep_before"] == True), "against + swept")
    group_stats((tr["trend_aligned"] == False) & (tr["sweep_before"] == False), "against + no sweep")


if __name__ == "__main__":
    main()
