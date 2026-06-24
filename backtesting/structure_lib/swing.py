"""
Step 1 — Swing Point Detection.

Pivot-based swing highs and swing lows.
No forced edge points (unlike smc library).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def swing_points(
    ohlc: pd.DataFrame,
    swing_length: int = 3,
    causal: bool = True,
) -> tuple[pd.Series, pd.Series]:
    """
    Detect swing highs and swing lows using a pivot method.

    A pivot at bar i requires high[i] to be the max (or low[i] the min) of
    high[i - swing_length : i + swing_length + 1].

    causal=True (default): label is placed at bar i + swing_length — the bar
    at which the right side of the window is fully visible. This is the only
    safe value for bar-loop backtesting and live trading. The level price is
    still the actual pivot bar's price.

    causal=False: label sits at the pivot bar i — has look-ahead bias because
    bars i+1..i+swing_length are not yet visible. Only use for visualization.

    When consecutive swings have the same type, the more extreme one
    (higher high / lower low) is kept.

    Parameters
    ----------
    ohlc : pd.DataFrame
        Must have columns: open, high, low, close.
    swing_length : int
        Number of candles to look on each side of a pivot (default 3).
        On 5m data this gives a ~35 min window (7 candles total).
    causal : bool
        Shift labels forward by swing_length to eliminate look-ahead (default True).

    Returns
    -------
    swings : pd.Series
        Same index as ohlc. Values: 1 (swing high), -1 (swing low), NaN.
    levels : pd.Series
        Price level of each swing point. NaN where no swing.
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    n = len(ohlc)

    swings = np.full(n, np.nan)
    levels = np.full(n, np.nan)

    # First/last `swing_length` candles cannot be pivots (not enough context)
    for i in range(swing_length, n - swing_length):
        left = i - swing_length
        right = i + swing_length + 1

        # Swing high?
        if high[i] == np.max(high[left:right]):
            # Ensure it's strictly the max (no ties with edge candles)
            # The rolling max at center means it's a local peak
            swings[i] = 1
            levels[i] = high[i]

        # Swing low?
        elif low[i] == np.min(low[left:right]):
            swings[i] = -1
            levels[i] = low[i]

    # ── Resolve consecutive same-type swings ──
    # Keep the more extreme one: higher high, lower low
    positions = np.where(~np.isnan(swings))[0]
    if len(positions) < 2:
        return pd.Series(swings, index=ohlc.index, name="swing"), \
               pd.Series(levels, index=ohlc.index, name="level")

    changed = True
    while changed:
        changed = False
        positions = np.where(~np.isnan(swings))[0]

        for idx in range(len(positions) - 1):
            p0, p1 = positions[idx], positions[idx + 1]

            if swings[p0] == swings[p1] == 1:
                # Two consecutive swing highs — keep the higher one
                if high[p0] >= high[p1]:
                    swings[p1] = np.nan
                    levels[p1] = np.nan
                else:
                    swings[p0] = np.nan
                    levels[p0] = np.nan
                changed = True
                break

            elif swings[p0] == swings[p1] == -1:
                # Two consecutive swing lows — keep the lower one
                if low[p0] <= low[p1]:
                    swings[p1] = np.nan
                    levels[p1] = np.nan
                else:
                    swings[p0] = np.nan
                    levels[p0] = np.nan
                changed = True
                break

    s = pd.Series(swings, index=ohlc.index, name="swing")
    l = pd.Series(levels, index=ohlc.index, name="level")

    if causal:
        # Shift forward so the label is visible only once the right side is confirmed.
        # .shift(n) moves values n positions forward, filling the head with NaN.
        s = s.shift(swing_length)
        l = l.shift(swing_length)

    return s, l


# ── Verification ─────────────────────────────────────────────


def debug_swings(ohlc: pd.DataFrame, n_days: int = 3, swing_length: int = 3) -> None:
    """
    Print swing points day by day for manual verification.
    Shows a condensed text view: each candle as a dot, swings as arrows.
    """
    swings, levels = swing_points(ohlc, swing_length=swing_length, causal=False)

    days = sorted(set(idx.date() for idx in ohlc.index))[:n_days]

    for day in days:
        day_mask = ohlc.index.date == day
        day_ohlc = ohlc[day_mask]
        day_swings = swings[day_mask]
        day_levels = levels[day_mask]

        print(f"\n═══ {day} ═══")
        print(f"{'Time':>8} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8}  Swing")
        print("-" * 55)

        swing_count = 0
        for i in range(len(day_ohlc)):
            ts = day_ohlc.index[i]
            o, h, l, c = day_ohlc.iloc[i][["open", "high", "low", "close"]]
            sv = day_swings.iloc[i]
            sl = day_levels.iloc[i]

            swing_str = ""
            if not np.isnan(sv):
                if sv == 1:
                    swing_str = f"↗ HIGH {sl:.5f}"
                else:
                    swing_str = f"↘ LOW {sl:.5f}"
                swing_count += 1

            print(f"{ts.strftime('%H:%M'):>8} {o:>8.5f} {h:>8.5f} {l:>8.5f} {c:>8.5f}  {swing_str}")

        print(f"  → {swing_count} swings on this day")


def stats(ohlc: pd.DataFrame, swing_length: int = 3) -> dict:
    """Return summary stats for verification."""
    swings, levels = swing_points(ohlc, swing_length=swing_length, causal=False)
    n_total = len(swings)
    n_highs = int((swings == 1).sum())
    n_lows = int((swings == -1).sum())
    n_swings = n_highs + n_lows

    # Compare with smc library
    from smartmoneyconcepts import smc
    smc_shl = smc.swing_highs_lows(ohlc, swing_length=swing_length)
    smc_highs = int((smc_shl["HighLow"] == 1).sum())
    smc_lows = int((smc_shl["HighLow"] == -1).sum())
    smc_total = smc_highs + smc_lows

    # Filter out forced edge points from smc count
    smc_edge_real = 0
    smc_positions = np.where(smc_shl["HighLow"].notna().values)[0]
    if len(smc_positions) > 0:
        if smc_positions[0] == 0:  # forced first
            smc_edge_real += 1
        if smc_positions[-1] == n_total - 1:  # forced last
            smc_edge_real += 1

    return {
        "n_candles": n_total,
        "n_swings": n_swings,
        "n_highs": n_highs,
        "n_lows": n_lows,
        "swings_per_day": round(n_swings / max((n_total / 288), 1), 1),
        "smc_total": smc_total,
        "smc_highs": smc_highs,
        "smc_lows": smc_lows,
        "smc_edge_fakes": smc_edge_real,
    }
