"""
Single-bar candle patterns.

Each function:
    - Takes OHLC arrays (numpy, same length)
    - Returns int array: +1 bullish, -1 bearish, 0 no signal
    - NaN-safe (handles missing bars)

Patterns: doji, hammer, shooting_star, pin_bar, marubozu, spinning_top.
"""

from __future__ import annotations

import numpy as np

from backtesting.features_v2.registry import registry


# ── Helpers ────────────────────────────────────────────────────────────────────

def _body(open: np.ndarray, close: np.ndarray) -> np.ndarray:
    return np.abs(close - open)


def _body_pct(open: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Body size as fraction of the bar's total range. NaN-safe."""
    body = _body(open, close)
    rng = _range(high, low)
    return np.divide(body, rng, out=np.zeros_like(body), where=rng > 0)


def _upper_wick(open: np.ndarray, high: np.ndarray, close: np.ndarray) -> np.ndarray:
    return np.where(close >= open, high - close, high - open)


def _lower_wick(open: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    return np.where(close >= open, open - low, close - low)


def _range(high: np.ndarray, low: np.ndarray) -> np.ndarray:
    return high - low


# ── Single-bar patterns ────────────────────────────────────────────────────────


@registry.register("doji", category="single")
def doji(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    threshold: float = 0.05,
) -> np.ndarray:
    """
    Doji: open ≈ close (very small body).
    
    Bullish when body < threshold × range and close > midpoint of range.
    Bearish when body < threshold × range and close < midpoint of range.
    """
    body_pct = _body_pct(open, high, low, close)
    is_doji = body_pct < threshold
    mid = (high + low) / 2
    bullish = is_doji & (close > mid)
    bearish = is_doji & (close < mid)
    return np.where(bullish, 1, np.where(bearish, -1, 0)).astype(np.int64)


@registry.register("hammer", category="single")
def hammer(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    lower_wick_ratio: float = 2.0,
    body_pct_max: float = 0.4,
) -> np.ndarray:
    """
    Hammer: small body at top, long lower wick ≥ 2× body.
    Bullish signal. Must appear in downtrend context (checked in pipeline).
    """
    body = _body(open, close)
    lw = _lower_wick(open, low, close)
    is_bullish = (lw >= lower_wick_ratio * body) & (_body_pct(open, high, low, close) <= body_pct_max)
    return np.where(is_bullish, 1, 0).astype(np.int64)


@registry.register("shooting_star", category="single")
def shooting_star(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    upper_wick_ratio: float = 2.0,
    body_pct_max: float = 0.4,
) -> np.ndarray:
    """
    Shooting star: small body at bottom, long upper wick ≥ 2× body.
    Bearish signal. Must appear in uptrend context.
    """
    body = _body(open, close)
    uw = _upper_wick(open, high, close)
    is_bearish = (uw >= upper_wick_ratio * body) & (_body_pct(open, high, low, close) <= body_pct_max)
    return np.where(is_bearish, -1, 0).astype(np.int64)


@registry.register("pin_bar", category="single")
def pin_bar(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    wick_ratio: float = 3.0,
    body_pct_max: float = 0.3,
) -> np.ndarray:
    """
    Pin bar: very long wick (≥ 3× body) on one side, small body.
    Direction determined by wick side. Requires trend context.
    """
    body = _body(open, close)
    lw = _lower_wick(open, low, close)
    uw = _upper_wick(open, high, close)
    small_body = _body_pct(open, high, low, close) <= body_pct_max
    bullish = small_body & (lw >= wick_ratio * body) & (lw > uw)
    bearish = small_body & (uw >= wick_ratio * body) & (uw > lw)
    return np.where(bullish, 1, np.where(bearish, -1, 0)).astype(np.int64)


@registry.register("marubozu", category="single")
def marubozu(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    wick_pct_max: float = 0.05,
) -> np.ndarray:
    """
    Marubozu: full body, no wicks (or very small).
    Bullish = close >> open (strong buyers). Bearish = open >> close (strong sellers).
    """
    rng = _range(high, low)
    body = _body(open, close)
    uw = _upper_wick(open, high, close)
    lw = _lower_wick(open, low, close)
    safe_rng = np.where(rng == 0, np.nan, rng)
    no_wicks = (uw / safe_rng <= wick_pct_max) & \
               (lw / safe_rng <= wick_pct_max) & \
               (body / safe_rng >= 0.9)
    bullish = no_wicks & (close > open)
    bearish = no_wicks & (close < open)
    return np.where(bullish, 1, np.where(bearish, -1, 0)).astype(np.int64)


@registry.register("spinning_top", category="single")
def spinning_top(
    open: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    body_pct_max: float = 0.3,
    wick_body_ratio_min: float = 1.0,
) -> np.ndarray:
    """
    Spinning top: small body centered, wicks on both sides ≥ body.
    Indecision pattern — often preceded reversal. Neutral.
    """
    bp = _body_pct(open, high, low, close)
    body = _body(open, close)
    uw = _upper_wick(open, high, close)
    lw = _lower_wick(open, low, close)
    both_wicks = (uw >= wick_body_ratio_min * body) & (lw >= wick_body_ratio_min * body)
    is_spin = (bp <= body_pct_max) & (bp > 0) & both_wicks
    return np.where(is_spin, 0, 0).astype(np.int64)  # neutral — indecision pattern
