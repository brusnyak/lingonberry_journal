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

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data.
    pools : list of LiquidityPool
        Known liquidity pools to check.
    lookback : int
        How many candles back to check for the break event.
    reclaim_candles : int
        Max candles for the close to reclaim the level after the break.

    Returns
    -------
    list of Sweep
        Sweep events in chronological order.
    """
    sweeps: list[Sweep] = []

    for i in range(len(ohlc)):
        if i < lookback:
            continue

        candle = ohlc.iloc[i]
        # Look back to see if any pool was swept in the last `lookback` candles
        for j in range(max(0, i - lookback), i + 1):
            test_candle = ohlc.iloc[j]
            for pool in pools:
                # Already detected this sweep?
                if any(s.sweep_time == ohlc.index[i] and s.pool == pool for s in sweeps):
                    continue

                broke = False
                wick_only = False
                direction = ""

                # Buy-side pool (high) — break above = sweep of BSL
                if pool.side == "buy":
                    if test_candle["high"] > pool.level:
                        broke = True
                        wick_only = test_candle["close"] <= pool.level
                        direction = "bearish"  # selling after BSL sweep

                # Sell-side pool (low) — break below = sweep of SSL
                elif pool.side == "sell":
                    if test_candle["low"] < pool.level:
                        broke = True
                        wick_only = test_candle["close"] >= pool.level
                        direction = "bullish"  # buying after SSL sweep

                if not broke:
                    continue

                # Check for reclaim within reclaim_candles after the break
                reclaim = False
                check_start = j + 1
                check_end = min(i + reclaim_candles + 1, len(ohlc))

                for k in range(check_start, check_end):
                    reclaim_candle = ohlc.iloc[k]
                    if pool.side == "buy":
                        # Close back below the level
                        if reclaim_candle["close"] < pool.level:
                            reclaim = True
                            break
                    elif pool.side == "sell":
                        # Close back above the level
                        if reclaim_candle["close"] > pool.level:
                            reclaim = True
                            break

                # Record sweep
                sweeps.append(Sweep(
                    pool=pool,
                    sweep_time=ohlc.index[i],
                    direction=direction,
                    reclaim=reclaim,
                    wick_only=wick_only,
                ))

    # Deduplicate and sort
    seen_keys: set[tuple] = set()
    unique: list[Sweep] = []
    for s in sweeps:
        key = (s.pool.level, s.direction, s.sweep_time)
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(s)

    unique.sort(key=lambda s: s.sweep_time)
    return unique
