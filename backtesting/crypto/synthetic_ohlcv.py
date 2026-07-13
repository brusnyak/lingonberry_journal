"""Synthetic OHLCV generators with a known, verifiable ground-truth direction.

Used to sanity-check the structure/direction measurement pipeline itself before
trusting a result (positive or null) on real market data: if the harness can't
detect a real, planted trend on data where the answer is known by construction,
the harness -- not the market -- is the problem.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_staircase_series(
    direction: str,
    *,
    bars: int = 20000,
    tf_minutes: int = 15,
    leg_bars: int = 40,
    pullback_bars: int = 15,
    leg_move_pct: float = 0.03,
    pullback_frac: float = 0.35,
    noise_std_pct: float = 0.001,
    start_price: float = 100.0,
    seed: int = 0,
) -> pd.DataFrame:
    """Alternating impulse + partial-pullback legs -- produces real HH/HL (or
    LH/LL) swing structure, not a monotonic line a pivot detector can't
    characterize. direction: 'up', 'down', or 'choppy' (equal legs, no net drift).
    """
    rng = np.random.default_rng(seed)
    closes = [start_price]
    i = 0
    leg_up = direction in ("up", "choppy")
    while len(closes) < bars:
        impulse_sign = 1 if (direction == "up" or (direction == "choppy" and leg_up)) else -1
        if direction == "down":
            impulse_sign = -1
        for _ in range(leg_bars):
            step = impulse_sign * leg_move_pct / leg_bars + rng.normal(0, noise_std_pct)
            closes.append(closes[-1] * (1 + step))
        pullback_sign = -impulse_sign
        pullback_total = leg_move_pct * pullback_frac
        for _ in range(pullback_bars):
            step = pullback_sign * pullback_total / pullback_bars + rng.normal(0, noise_std_pct)
            closes.append(closes[-1] * (1 + step))
        leg_up = not leg_up
    closes = np.array(closes[:bars])

    opens = np.roll(closes, 1)
    opens[0] = start_price
    intrabar = np.abs(rng.normal(0, noise_std_pct * 1.5, size=bars))
    highs = np.maximum(opens, closes) * (1 + intrabar)
    lows = np.minimum(opens, closes) * (1 - intrabar)

    ts = pd.date_range("2024-01-01", periods=bars, freq=f"{tf_minutes}min", tz="UTC")
    return pd.DataFrame({
        "ts": ts, "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": np.full(bars, 1.0),
    })


def make_random_walk_series(
    *,
    bars: int = 20000,
    tf_minutes: int = 15,
    step_std_pct: float = 0.003,
    start_price: float = 100.0,
    seed: int = 0,
) -> pd.DataFrame:
    """Zero-drift random walk -- negative control, direction accuracy must be ~50%."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, step_std_pct, size=bars)
    closes = start_price * np.cumprod(1 + steps)
    opens = np.roll(closes, 1)
    opens[0] = start_price
    intrabar = np.abs(rng.normal(0, step_std_pct * 0.5, size=bars))
    highs = np.maximum(opens, closes) * (1 + intrabar)
    lows = np.minimum(opens, closes) * (1 - intrabar)
    ts = pd.date_range("2024-01-01", periods=bars, freq=f"{tf_minutes}min", tz="UTC")
    return pd.DataFrame({
        "ts": ts, "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": np.full(bars, 1.0),
    })
