"""
Multi-bar candle patterns.

Each function:
    - Takes OHLC arrays (numpy, same length)
    - Returns int array: +1 bullish, -1 bearish, 0 no signal
    - Elements before the pattern window are 0 (no signal)

Patterns: engulfing, harami, morning_star, evening_star,
          piercing, dark_cloud_cover, three_soldiers, three_crows, inside_bar.
"""

from __future__ import annotations

import numpy as np

from backtesting.features_v2.registry import registry
from backtesting.features_v2.candle import _body, _body_pct


# ── 2-bar patterns ─────────────────────────────────────────────────────────────


@registry.register("bullish_engulfing", category="multi", params={"bars": 2})
def bullish_engulfing(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """
    Bullish engulfing: red bar followed by larger green bar that engulfs it.
    Requires downtrend context.
    """
    if len(close) < 2:
        return np.zeros(len(close), dtype=np.int64)

    signal = np.zeros(len(close), dtype=np.int64)
    for i in range(1, len(close)):
        prev_red = close[i - 1] < open[i - 1]
        curr_green = close[i] > open[i]
        engulfs = open[i] < close[i - 1] and close[i] > open[i - 1]
        if prev_red and curr_green and engulfs:
            signal[i] = 1
    return signal


@registry.register("bearish_engulfing", category="multi", params={"bars": 2})
def bearish_engulfing(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """
    Bearish engulfing: green bar followed by larger red bar that engulfs it.
    Requires uptrend context.
    """
    if len(close) < 2:
        return np.zeros(len(close), dtype=np.int64)

    signal = np.zeros(len(close), dtype=np.int64)
    for i in range(1, len(close)):
        prev_green = close[i - 1] > open[i - 1]
        curr_red = close[i] < open[i]
        engulfs = open[i] > close[i - 1] and close[i] < open[i - 1]
        if prev_green and curr_red and engulfs:
            signal[i] = -1
    return signal


@registry.register("bullish_harami", category="multi", params={"bars": 2})
def bullish_harami(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """
    Bullish harami: red bar followed by smaller green bar inside its body.
    Possible reversal in downtrend.

    Red bar body: close[0] (bottom) → open[0] (top).
    Green bar is inside when its open > red's close AND its close < red's open.
    """
    if len(close) < 2:
        return np.zeros(len(close), dtype=np.int64)

    signal = np.zeros(len(close), dtype=np.int64)
    for i in range(1, len(close)):
        prev_red = close[i - 1] < open[i - 1]
        curr_green = close[i] > open[i]
        inside = open[i] > close[i - 1] and close[i] < open[i - 1]
        if prev_red and curr_green and inside:
            signal[i] = 1
    return signal


@registry.register("bearish_harami", category="multi", params={"bars": 2})
def bearish_harami(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """
    Bearish harami: green bar followed by smaller red bar inside its body.
    Possible reversal in uptrend.

    Green bar body: open[0] (bottom) → close[0] (top).
    Red bar is inside when its open < green's close AND its close > green's open.
    """
    if len(close) < 2:
        return np.zeros(len(close), dtype=np.int64)

    signal = np.zeros(len(close), dtype=np.int64)
    for i in range(1, len(close)):
        prev_green = close[i - 1] > open[i - 1]
        curr_red = close[i] < open[i]
        inside = open[i] < close[i - 1] and close[i] > open[i - 1]
        if prev_green and curr_red and inside:
            signal[i] = -1
    return signal


@registry.register("piercing", category="multi", params={"bars": 2})
def piercing(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """
    Piercing pattern (bullish reversal):
    Red bar day 1 → green bar day 2 opens lower but closes above midpoint of day 1.
    """
    if len(close) < 2:
        return np.zeros(len(close), dtype=np.int64)

    signal = np.zeros(len(close), dtype=np.int64)
    for i in range(1, len(close)):
        prev_red = close[i - 1] < open[i - 1]
        curr_green = close[i] > open[i]
        opens_lower = open[i] < low[i - 1]
        closes_above_mid = close[i] > (open[i - 1] + close[i - 1]) / 2
        if prev_red and curr_green and opens_lower and closes_above_mid:
            signal[i] = 1
    return signal


@registry.register("dark_cloud_cover", category="multi", params={"bars": 2})
def dark_cloud_cover(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """
    Dark cloud cover (bearish reversal):
    Green bar day 1 → red bar day 2 opens higher but closes below midpoint of day 1.
    """
    if len(close) < 2:
        return np.zeros(len(close), dtype=np.int64)

    signal = np.zeros(len(close), dtype=np.int64)
    for i in range(1, len(close)):
        prev_green = close[i - 1] > open[i - 1]
        curr_red = close[i] < open[i]
        opens_higher = open[i] > high[i - 1]
        closes_below_mid = close[i] < (open[i - 1] + close[i - 1]) / 2
        if prev_green and curr_red and opens_higher and closes_below_mid:
            signal[i] = -1
    return signal


# ── 3-bar patterns ─────────────────────────────────────────────────────────────


@registry.register("morning_star", category="multi", params={"bars": 3})
def morning_star(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    doji_threshold: float = 0.05,
) -> np.ndarray:
    """
    Morning star (bullish reversal, 3 bars):
    1. Red bar (downtrend)
    2. Small body (doji-like), close below prior close (loss of sell momentum)
    3. Green bar closes above midpoint of bar 1

    Forex-adapted: no literal price gap required (24/5 market has none intraday).
    The doji bar must close below prior close, showing inability to rally.
    """
    if len(close) < 3:
        return np.zeros(len(close), dtype=np.int64)

    signal = np.zeros(len(close), dtype=np.int64)
    for i in range(2, len(close)):
        b1_red = close[i - 2] < open[i - 2]
        b2_small = _body_pct(open[i - 1:i], high[i - 1:i], low[i - 1:i], close[i - 1:i])[0] < doji_threshold
        b2_below = close[i - 1] < close[i - 2]  # doji close below prior close
        b3_green = close[i] > open[i]
        b3_close_above = close[i] > (open[i - 2] + close[i - 2]) / 2
        if b1_red and b2_small and b2_below and b3_green and b3_close_above:
            signal[i] = 1
    return signal


@registry.register("evening_star", category="multi", params={"bars": 3})
def evening_star(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    doji_threshold: float = 0.05,
) -> np.ndarray:
    """
    Evening star (bearish reversal, 3 bars):
    1. Green bar (uptrend)
    2. Small body (doji-like), close above prior close (loss of buy momentum)
    3. Red bar closes below midpoint of bar 1

    Forex-adapted: no literal price gap required (24/5 market has none intraday).
    The doji bar must close above prior close, showing inability to sell off.
    """
    if len(close) < 3:
        return np.zeros(len(close), dtype=np.int64)

    signal = np.zeros(len(close), dtype=np.int64)
    for i in range(2, len(close)):
        b1_green = close[i - 2] > open[i - 2]
        b2_small = _body_pct(open[i - 1:i], high[i - 1:i], low[i - 1:i], close[i - 1:i])[0] < doji_threshold
        b2_above = close[i - 1] > close[i - 2]  # doji close above prior close
        b3_red = close[i] < open[i]
        b3_close_below = close[i] < (open[i - 2] + close[i - 2]) / 2
        if b1_green and b2_small and b2_above and b3_red and b3_close_below:
            signal[i] = -1
    return signal


@registry.register("three_soldiers", category="multi", params={"bars": 3})
def three_white_soldiers(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """
    Three white soldiers (bullish continuation/reversal):
    3 consecutive green bars, each closing higher, each opening within previous body.
    """
    if len(close) < 3:
        return np.zeros(len(close), dtype=np.int64)

    signal = np.zeros(len(close), dtype=np.int64)
    for i in range(2, len(close)):
        all_green = all(close[j] > open[j] for j in range(i - 2, i + 1))
        higher_closes = all(close[j] > close[j - 1] for j in range(i - 1, i + 1))
        opens_within = all(
            open[j] > open[j - 1] and open[j] < close[j - 1]
            for j in range(i - 1, i + 1)
        )
        if all_green and higher_closes and opens_within:
            signal[i] = 1
    return signal


@registry.register("three_crows", category="multi", params={"bars": 3})
def three_black_crows(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """
    Three black crows (bearish continuation/reversal):
    3 consecutive red bars, each closing lower, each opening within previous body.
    """
    if len(close) < 3:
        return np.zeros(len(close), dtype=np.int64)

    signal = np.zeros(len(close), dtype=np.int64)
    for i in range(2, len(close)):
        all_red = all(close[j] < open[j] for j in range(i - 2, i + 1))
        lower_closes = all(close[j] < close[j - 1] for j in range(i - 1, i + 1))
        opens_within = all(
            open[j] < open[j - 1] and open[j] > close[j - 1]
            for j in range(i - 1, i + 1)
        )
        if all_red and lower_closes and opens_within:
            signal[i] = -1
    return signal


@registry.register("inside_bar", category="multi", params={"bars": 2})
def inside_bar(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """
    Inside bar breakout: bar[i] is consolidation, bar[i+1] breaks out.

    Signal fires on the breakout bar (i+1) when it closes beyond the
    mother bar's (i) high/low. Bullish = close above mother's high,
    bearish = close below mother's low.

    Mother bar must be the immediately preceding bar.
    """
    n = len(close)
    if n < 3:
        return np.zeros(n, dtype=np.int64)

    signal = np.zeros(n, dtype=np.int64)
    for i in range(1, n - 1):
        mother_inside = high[i] < high[i - 1] and low[i] > low[i - 1]
        if mother_inside:
            if close[i + 1] > high[i - 1]:
                signal[i + 1] = 1  # upside breakout
            elif close[i + 1] < low[i - 1]:
                signal[i + 1] = -1  # downside breakout
    return signal
