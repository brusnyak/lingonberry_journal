"""
Step 3c — Fair Value Gap (FVG) Detection.

A 3-candle imbalance pattern:
  Bullish FVG: candle 3 low > candle 1 high  (gap up — price jumped over a range)
  Bearish FVG: candle 3 high < candle 1 low  (gap down — price dropped over a range)

The middle candle (c2) is the displacement candle that created the gap.
Entry zone is the gap itself. CE (Consequent Encroachment) = 50% midpoint.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd


class FVG(NamedTuple):
    kind: str  # "bullish" or "bearish"
    top: float    # upper bound of the gap
    bottom: float # lower bound of the gap
    ce: float     # midpoint (consequent encroachment)
    c2_time: pd.Timestamp  # displacement candle
    c1_idx: int
    c2_idx: int
    c3_idx: int


def detect_fvgs(
    ohlc: pd.DataFrame,
    min_gap_points: float | None = None,
) -> list[FVG]:
    """
    Detect Fair Value Gaps (3-candle imbalances).

    Parameters
    ----------
    ohlc : pd.DataFrame
        Must have 'open', 'high', 'low', 'close' columns.
    min_gap_points : float or None
        Minimum gap size in price units to qualify.
        If None, auto-computes as 1% of ATR14.

    Returns
    -------
    list of FVG
    """
    if min_gap_points is None:
        # Compute ATR14-based minimum
        high = ohlc["high"].values
        low = ohlc["low"].values
        close = ohlc["close"].values
        tr = np.maximum(high[1:] - low[1:], np.abs(high[1:] - close[:-1]))
        tr = np.maximum(tr, np.abs(low[1:] - close[:-1]))
        atr14 = np.mean(tr[:14]) if len(tr) >= 14 else np.mean(tr)
        min_gap_points = atr14 * 0.01  # 1% of ATR — tiny threshold

    fvgs: list[FVG] = []
    high = ohlc["high"].values
    low = ohlc["low"].values

    for i in range(2, len(ohlc)):
        c1_high = high[i - 2]
        c1_low = low[i - 2]
        c3_high = high[i]
        c3_low = low[i]

        # Bullish FVG: c3_low > c1_high
        if c3_low > c1_high:
            gap_top = c3_low
            gap_bottom = c1_high
            gap_size = gap_top - gap_bottom

            if gap_size >= min_gap_points:
                fvgs.append(FVG(
                    kind="bullish",
                    top=float(gap_top),
                    bottom=float(gap_bottom),
                    ce=float((gap_top + gap_bottom) / 2.0),
                    c2_time=ohlc.index[i - 1],
                    c1_idx=i - 2,
                    c2_idx=i - 1,
                    c3_idx=i,
                ))

        # Bearish FVG: c3_high < c1_low
        elif c3_high < c1_low:
            gap_top = c1_low
            gap_bottom = c3_high
            gap_size = gap_top - gap_bottom

            if gap_size >= min_gap_points:
                fvgs.append(FVG(
                    kind="bearish",
                    top=float(gap_top),
                    bottom=float(gap_bottom),
                    ce=float((gap_top + gap_bottom) / 2.0),
                    c2_time=ohlc.index[i - 1],
                    c1_idx=i - 2,
                    c2_idx=i - 1,
                    c3_idx=i,
                ))

    return fvgs


def unmitigated_fvgs(
    fvgs: list[FVG],
    ohlc: pd.DataFrame,
    current_idx: int,
) -> list[FVG]:
    """Return FVGs that have not been fully filled (mitigated) yet."""
    result: list[FVG] = []
    for fvg in fvgs:
        if fvg.c3_idx >= current_idx:
            continue  # FVG hasn't formed yet at this point

        # Check if any candle after c3 has filled the entire gap
        filled = False
        for i in range(fvg.c3_idx + 1, min(current_idx, len(ohlc))):
            candle = ohlc.iloc[i]
            if fvg.kind == "bullish":
                # Bullish FVG is filled when price trades down into the gap
                if candle["low"] <= fvg.top:
                    filled = True
                    break
            else:
                # Bearish FVG is filled when price trades up into the gap
                if candle["high"] >= fvg.bottom:
                    filled = True
                    break

        if not filled:
            result.append(fvg)

    return result
