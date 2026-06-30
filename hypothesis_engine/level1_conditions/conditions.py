"""
Individual ICT/SMC structure condition detectors.

Each function takes OHLCV arrays and returns a signal array:
  +1  → long bias (condition suggests buy)
  -1  → short bias (condition suggests sell)
   0  → no signal

Functions are pure numpy — no data loading, no pandas.
"""

from __future__ import annotations

import numpy as np
from numba import njit


# ── Swing point detection ────────────────────────────────────────────

@njit
def _swing_highs(highs: np.ndarray, lookback: int = 5) -> np.ndarray:
    """Boolean array: True where bar is a swing high."""
    n = len(highs)
    out = np.zeros(n, dtype=np.bool_)
    for i in range(lookback, n - lookback):
        h = highs[i]
        is_high = True
        for j in range(1, lookback + 1):
            if highs[i - j] >= h or highs[i + j] >= h:
                is_high = False
                break
        if is_high:
            out[i] = True
    return out


@njit
def _swing_lows(lows: np.ndarray, lookback: int = 5) -> np.ndarray:
    """Boolean array: True where bar is a swing low."""
    n = len(lows)
    out = np.zeros(n, dtype=np.bool_)
    for i in range(lookback, n - lookback):
        l = lows[i]
        is_low = True
        for j in range(1, lookback + 1):
            if lows[i - j] <= l or lows[i + j] <= l:
                is_low = False
                break
        if is_low:
            out[i] = True
    return out


@njit
def _last_swing_idx(swings: np.ndarray) -> np.ndarray:
    """For each bar, index of the most recent swing point (-1 if none)."""
    n = len(swings)
    out = np.full(n, -1, dtype=np.int64)
    last_idx = -1
    for i in range(n):
        if swings[i]:
            last_idx = i
        out[i] = last_idx
    return out


# ── Condition 1: Sweep (liquidity grab) ──────────────────────────────

def sweep(
    open: np.ndarray, high: np.ndarray,
    low: np.ndarray, close: np.ndarray,
    lookback: int = 5,
) -> np.ndarray:
    """
    Sweep detection.

    A sweep occurs when price briefly breaks a recent swing level
    (HH for long sweep, LL for short sweep) and the bar closes back
    on the other side — indicating the break was rejected.

    Returns: +1 for long sweep (broke above swing high, rejected)
             -1 for short sweep (broke below swing low, rejected)
              0 otherwise
    """
    n = len(close)
    sh = _swing_highs(high, lookback)
    sl = _swing_lows(low, lookback)

    last_sh_idx = _last_swing_idx(sh)
    last_sl_idx = _last_swing_idx(sl)

    signal = np.zeros(n, dtype=np.int64)

    # Avoid numba issues with variable stride
    for i in range(1, n):
        # Long sweep: break above recent swing high, close back below it
        if last_sh_idx[i] >= 0:
            sv = high[last_sh_idx[i]]
            if high[i] > sv and close[i] < sv:
                signal[i] = 1

        # Short sweep: break below recent swing low, close back above it
        if last_sl_idx[i] >= 0:
            sv = low[last_sl_idx[i]]
            if low[i] < sv and close[i] > sv:
                signal[i] = -1

    return signal


# ── Condition 2: Break of Structure (BOS) ────────────────────────────

def bos(
    open: np.ndarray, high: np.ndarray,
    low: np.ndarray, close: np.ndarray,
    lookback: int = 5,
) -> np.ndarray:
    """
    Break of Structure.

    Bullish BOS: price breaks ABOVE a swing high with conviction
    (close above the swing high).
    Bearish BOS: price breaks BELOW a swing low with conviction
    (close below the swing low).

    Unlike sweeps, BOS is a confirmed break — close is ON the other side.

    Returns: +1 for bullish BOS, -1 for bearish BOS, 0 otherwise.
    """
    n = len(close)
    sh = _swing_highs(high, lookback)
    sl = _swing_lows(low, lookback)

    last_sh_idx = _last_swing_idx(sh)
    last_sl_idx = _last_swing_idx(sl)

    signal = np.zeros(n, dtype=np.int64)

    for i in range(1, n):
        if last_sh_idx[i] >= 0:
            sv = high[last_sh_idx[i]]
            if close[i] > sv:
                signal[i] = 1

        if last_sl_idx[i] >= 0:
            sv = low[last_sl_idx[i]]
            if close[i] < sv:
                signal[i] = -1

    return signal


# ── Condition 2b: Structure-aware BOS (HH/HL, LL/LH) ─────────────────

def bos_structured(
    open: np.ndarray, high: np.ndarray,
    low: np.ndarray, close: np.ndarray,
    lookback: int = 5,
) -> np.ndarray:
    """
    Structure-aware Break of Structure.

    Only fires when market structure aligns with the break direction:
      - Bullish BOS only when in HH/HL structure (uptrend)
      - Bearish BOS only when in LL/LH structure (downtrend)
      - No signal in ranging / undefined structure

    HH/HL = last 2 swing highs higher AND last 2 swing lows higher
    LL/LH = last 2 swing highs lower  AND last 2 swing lows lower

    Returns: +1 for bullish, -1 for bearish, 0 otherwise.
    """
    n = len(close)
    sh = _swing_highs(high, lookback)
    sl = _swing_lows(low, lookback)

    signal = np.zeros(n, dtype=np.int64)

    for i in range(1, n):
        # Find last 2 swing highs
        last_sh = -1
        prev_sh = -1
        for j in range(i - 1, -1, -1):
            if sh[j]:
                if last_sh == -1:
                    last_sh = j
                elif prev_sh == -1:
                    prev_sh = j
                    break

        # Find last 2 swing lows
        last_sl = -1
        prev_sl = -1
        for j in range(i - 1, -1, -1):
            if sl[j]:
                if last_sl == -1:
                    last_sl = j
                elif prev_sl == -1:
                    prev_sl = j
                    break

        # Determine structure
        uptrend = False
        downtrend = False
        if prev_sh >= 0 and prev_sl >= 0:
            hh = high[last_sh] > high[prev_sh]  # higher high
            hl = low[last_sl] > low[prev_sl]    # higher low
            lh = high[last_sh] < high[prev_sh]  # lower high
            ll = low[last_sl] < low[prev_sl]    # lower low
            uptrend = hh and hl
            downtrend = lh and ll

        # Bullish BOS: break above swing high in uptrend
        if uptrend and last_sh >= 0:
            if close[i] > high[last_sh]:
                signal[i] = 1

        # Bearish BOS: break below swing low in downtrend
        elif downtrend and last_sl >= 0:
            if close[i] < low[last_sl]:
                signal[i] = -1

    return signal


# ── Condition 3: Change of Character (CHoCH) ─────────────────────────

def choch(
    open: np.ndarray, high: np.ndarray,
    low: np.ndarray, close: np.ndarray,
    lookback: int = 5,
) -> np.ndarray:
    """
    Change of Character.

    CHoCH is a swing point break AGAINST the last structure direction.

    In an uptrend (higher swing highs AND higher swing lows), a break
    below the most recent swing low signals a CHoCH to bearish.

    In a downtrend (lower swing highs AND lower swing lows), a break
    above the most recent swing high signals a CHoCH to bullish.

    Simplified: compare the last TWO swing highs to determine trend
    direction, then look for a break in the opposite direction.

    Returns: +1 for bullish CHoCH (broke above swing high after
              downtrend), -1 for bearish CHoCH (broke below swing
              low after uptrend), 0 otherwise.
    """
    n = len(close)
    sh = _swing_highs(high, lookback)
    sl = _swing_lows(low, lookback)

    signal = np.zeros(n, dtype=np.int64)

    for i in range(1, n):
        # Find last 2 swing highs
        last2_sh = -1
        last_sh = -1
        for j in range(i - 1, -1, -1):
            if sh[j]:
                if last_sh == -1:
                    last_sh = j
                elif last2_sh == -1:
                    last2_sh = j
                    break

        # Find last 2 swing lows
        last2_sl = -1
        last_sl = -1
        for j in range(i - 1, -1, -1):
            if sl[j]:
                if last_sl == -1:
                    last_sl = j
                elif last2_sl == -1:
                    last2_sl = j
                    break

        # Determine trend: if last 2 swing highs and lows are higher → uptrend
        if last2_sh >= 0 and last2_sl >= 0:
            uptrend = (
                high[last_sh] > high[last2_sh] and
                low[last_sl] > low[last2_sl]
            )
            downtrend = (
                high[last_sh] < high[last2_sh] and
                low[last_sl] < low[last2_sl]
            )

            if uptrend and last_sl >= 0:
                if low[i] < low[last_sl]:
                    signal[i] = -1  # bearish CHoCH
            elif downtrend and last_sh >= 0:
                if high[i] > high[last_sh]:
                    signal[i] = 1   # bullish CHoCH

    return signal


# ── Condition 4: Fair Value Gap (FVG) ────────────────────────────────

def fvg(
    open: np.ndarray, high: np.ndarray,
    low: np.ndarray, close: np.ndarray,
    gap_threshold: float = 0.00001,
) -> np.ndarray:
    """
    Fair Value Gap detection.

    A bullish FVG occurs when:
      low[bar+2] > high[bar]   (gap between bar 1 and bar 3, bar 2 creates it)

    A bearish FVG occurs when:
      high[bar+2] < low[bar]

    The gap midpoint is potential support/resistance.

    Returns:
      +1 for bullish FVG (gap up, price may retrace to fill)
      -1 for bearish FVG (gap down, price may retrace to fill)
       0 otherwise
    """
    n = len(close)
    signal = np.zeros(n, dtype=np.int64)

    for i in range(n - 2):
        # Bullish FVG: gap up
        if low[i + 2] > high[i] + gap_threshold:
            signal[i + 1] = 1  # signal on the middle bar
        # Bearish FVG: gap down
        elif high[i + 2] < low[i] - gap_threshold:
            signal[i + 1] = -1

    return signal


# ── Condition 5: Price relative to SMA ───────────────────────────────

def sma_cross(
    close: np.ndarray,
    period: int = 20,
    **kwargs,
) -> np.ndarray:
    """
    Price relative to SMA.

    +1 when close > SMA(period) — bullish bias
    -1 when close < SMA(period) — bearish bias
     0 otherwise (shouldn't happen unless close == SMA, rare)

    Note: this produces a signal on EVERY bar, not just transitions.
    Use sma_cross_change() for crossover detection.
    """
    signal = np.zeros(len(close), dtype=np.int64)
    if len(close) < period + 1:
        return signal

    sma = np.full(len(close), np.nan)
    cum = np.cumsum(close)
    sma[period - 1:] = (cum[period - 1:] - np.concatenate([[0], cum[:-period]])) / period

    for i in range(period, len(close)):
        if close[i] > sma[i]:
            signal[i] = 1
        elif close[i] < sma[i]:
            signal[i] = -1

    return signal


def sma_cross_change(
    close: np.ndarray,
    period: int = 20,
    **kwargs,
) -> np.ndarray:
    """
    SMA crossover change points only.

    +1 when price crosses ABOVE the SMA
    -1 when price crosses BELOW the SMA
     0 otherwise
    """
    n = len(close)
    signal = np.zeros(n, dtype=np.int64)
    if n < period + 2:
        return signal

    sma = np.full(n, np.nan)
    cum = np.cumsum(close)
    sma[period - 1:] = (cum[period - 1:] - np.concatenate([[0], cum[:-period]])) / period

    for i in range(period + 1, n):
        above_before = close[i - 1] > sma[i - 1]
        above_now = close[i] > sma[i]
        if above_now and not above_before:
            signal[i] = 1   # cross above
        elif not above_now and above_before:
            signal[i] = -1  # cross below

    return signal


# ── Condition 6: Inside Bar ──────────────────────────────────────────

def inside_bar(
    open: np.ndarray, high: np.ndarray,
    low: np.ndarray, close: np.ndarray,
) -> np.ndarray:
    """
    Inside Bar detection.

    An inside bar occurs when the current bar's high is <= previous bar's
    high AND current bar's low is >= previous bar's low.

    Inside bars suggest contraction / consolidation.
    Breakouts from inside bars can be directional.

    Returns: +1 for bullish inside bar tendency (close in upper half)
             -1 for bearish inside bar tendency (close in lower half)
              0 otherwise
    """
    n = len(close)
    signal = np.zeros(n, dtype=np.int64)

    for i in range(1, n):
        if high[i] <= high[i - 1] and low[i] >= low[i - 1]:
            # Inside bar — bias based on where close sits
            midpoint = (high[i] + low[i]) / 2
            if close[i] > midpoint:
                signal[i] = 1
            elif close[i] < midpoint:
                signal[i] = -1

    return signal


# ── Condition 7: Engulfing Bar ───────────────────────────────────────

def engulfing(
    open: np.ndarray, high: np.ndarray,
    low: np.ndarray, close: np.ndarray,
) -> np.ndarray:
    """
    Engulfing bar detection.

    Bullish engulfing: current bar open < previous close AND close > previous open
    Bearish engulfing: current bar open > previous close AND close < previous open

    Body of current bar completely engulfs body of previous bar.

    Returns: +1 for bullish engulfing, -1 for bearish engulfing, 0 otherwise.
    """
    n = len(close)
    signal = np.zeros(n, dtype=np.int64)

    for i in range(1, n):
        prev_body_top = max(open[i - 1], close[i - 1])
        prev_body_bot = min(open[i - 1], close[i - 1])
        body_top = max(open[i], close[i])
        body_bot = min(open[i], close[i])

        if body_bot < prev_body_bot and body_top > prev_body_top:
            if close[i] > open[i]:  # green bar
                signal[i] = 1
            else:
                signal[i] = -1

    return signal


# ── Condition 8: Outside Bar (Reversal) ──────────────────────────────

def outside_bar(
    open: np.ndarray, high: np.ndarray,
    low: np.ndarray, close: np.ndarray,
) -> np.ndarray:
    """
    Outside Bar (reversal) detection.

    Current bar has higher high AND lower low than previous bar.
    Indicates volatility expansion / potential reversal.

    Returns: +1 if close in upper half (bullish), -1 if lower half (bearish).
    """
    n = len(close)
    signal = np.zeros(n, dtype=np.int64)

    for i in range(1, n):
        if high[i] > high[i - 1] and low[i] < low[i - 1]:
            midpoint = (high[i] + low[i]) / 2
            if close[i] > midpoint:
                signal[i] = 1
            elif close[i] < midpoint:
                signal[i] = -1

    return signal


# ── Map for test harness ─────────────────────────────────────────────

CONDITIONS: dict[str, callable] = {
    "sweep": sweep,
    "bos": bos,
    "bos_struct": bos_structured,
    "choch": choch,
    "fvg": fvg,
    "sma": sma_cross,
    "sma_x": sma_cross_change,
    "inside_bar": inside_bar,
    "engulfing": engulfing,
    "outside_bar": outside_bar,
}
