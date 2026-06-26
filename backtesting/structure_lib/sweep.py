"""
Step 3b — Liquidity Pool & Sweep Detection.

Detect:
1. Liquidity pools: session extremes, swing points, prior-day levels
2. Sweeps: price breaks a pool level, then closes back inside within N candles
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd

from backtesting.structure_lib.sessions import SESSION_NAMES


class LiquidityPool(NamedTuple):
    level: float
    side: str  # "buy" (BSL above highs) or "sell" (SSL below lows)
    source: str  # "asia_high", "london_low", "prior_day_high", "swing_high", etc.
    time: pd.Timestamp | None


class Sweep(NamedTuple):
    pool: LiquidityPool
    sweep_time: pd.Timestamp
    direction: str  # "bullish" (swept sell-side, reversal up) or "bearish" (swept buy-side, reversal down)
    reclaim: bool  # True = close back inside the pool level
    wick_only: bool  # True = wick broke level but close didn't confirm


def detect_pools(
    ohlc: pd.DataFrame,
    swings: pd.Series,
    swing_levels: pd.Series,
) -> list[LiquidityPool]:
    """
    Build a list of known liquidity pools visible from the current data.

    Returns
    -------
    list of LiquidityPool
        Sorted by level ascending.
    """
    pools: list[LiquidityPool] = []
    seen: set[float] = set()

    # 1. Session extremes for each completed session today
    for name, (start_h, end_h) in SESSION_NAMES.items():
        for day, group in ohlc.groupby(ohlc.index.date):
            if end_h == 24:
                mask = group.index.hour >= start_h
            else:
                mask = (group.index.hour >= start_h) & (group.index.hour < end_h)

            sess = group[mask]
            if len(sess) == 0:
                continue

            sess_high = sess["high"].max()
            sess_low = sess["low"].min()

            if sess_high not in seen:
                pools.append(LiquidityPool(
                    level=float(sess_high),
                    side="buy",
                    source=f"{name}_high",
                    time=sess.index[-1],
                ))
                seen.add(sess_high)

            if sess_low not in seen:
                pools.append(LiquidityPool(
                    level=float(sess_low),
                    side="sell",
                    source=f"{name}_low",
                    time=sess.index[-1],
                ))
                seen.add(sess_low)

    # 2. Prior day high/low
    dates = sorted(set(ohlc.index.date))
    if len(dates) >= 2:
        prev = ohlc[ohlc.index.date == dates[-2]]
        pdh = float(prev["high"].max())
        pdl = float(prev["low"].min())

        if pdh not in seen:
            pools.append(LiquidityPool(level=pdh, side="buy", source="prior_day_high", time=None))
            seen.add(pdh)
        if pdl not in seen:
            pools.append(LiquidityPool(level=pdl, side="sell", source="prior_day_low", time=None))
            seen.add(pdl)

    # 3. Swing point extremes (visible swings)
    swing_indices = np.where(~np.isnan(swings.values))[0]
    if len(swing_indices) > 0:
        actual_indices = swings.index[swing_indices]
        for idx in actual_indices[-20:]:  # last 20 swings max
            sv = swings.loc[idx]
            level = float(swing_levels.loc[idx])
            if level in seen:
                continue

            if sv == 1:  # swing high
                pools.append(LiquidityPool(
                    level=level,
                    side="buy",
                    source="swing_high",
                    time=idx,
                ))
            elif sv == -1:  # swing low
                pools.append(LiquidityPool(
                    level=level,
                    side="sell",
                    source="swing_low",
                    time=idx,
                ))
            seen.add(level)

    pools.sort(key=lambda p: p.level)
    return pools


def detect_sweeps(
    ohlc: pd.DataFrame,
    pools: list[LiquidityPool],
    lookback: int = 3,
    reclaim_candles: int = 3,
) -> list[Sweep]:
    """
    Detect liquidity sweeps: price breaks a pool level and reclaims it.

    Only creates ONE sweep per pool per break event (at the break candle),
    not retrospectively on subsequent candles.
    """
    n = len(ohlc)
    high = ohlc["high"].to_numpy(dtype=float)
    low = ohlc["low"].to_numpy(dtype=float)
    close = ohlc["close"].to_numpy(dtype=float)
    times = ohlc.index.to_numpy()

    sweeps: list[Sweep] = []
    seen: set[tuple[float, str, int]] = set()  # (pool_level, direction, break_idx)

    buy_pools = [(p.level, p) for p in pools if p.side == "buy"]
    sell_pools = [(p.level, p) for p in pools if p.side == "sell"]

    for i in range(lookback, n):
        # Buy-side pools — check if THIS candle broke the level
        for level, pool in buy_pools:
            if not (high[i] > level):
                continue

            key = (level, "bearish", i)
            if key in seen:
                continue
            seen.add(key)

            wick = close[i] <= level

            # Reclaim check
            reclaim = False
            check_end = min(i + reclaim_candles + 1, n)
            for k in range(i + 1, check_end):
                if close[k] < level:
                    reclaim = True
                    break

            sweeps.append(Sweep(
                pool=pool, sweep_time=pd.Timestamp(times[i]),
                direction="bearish", reclaim=reclaim, wick_only=wick,
            ))

        # Sell-side pools
        for level, pool in sell_pools:
            if not (low[i] < level):
                continue

            key = (level, "bullish", i)
            if key in seen:
                continue
            seen.add(key)

            wick = close[i] >= level

            reclaim = False
            check_end = min(i + reclaim_candles + 1, n)
            for k in range(i + 1, check_end):
                if close[k] > level:
                    reclaim = True
                    break

            sweeps.append(Sweep(
                pool=pool, sweep_time=pd.Timestamp(times[i]),
                direction="bullish", reclaim=reclaim, wick_only=wick,
            ))

    sweeps.sort(key=lambda s: s.sweep_time)
    return sweeps
