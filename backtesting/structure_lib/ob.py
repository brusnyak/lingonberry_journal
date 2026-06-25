"""
Step 3d — Order Block Detection.

An Order Block is the last opposing candle BEFORE a displacement move.

- Bullish OB: last BEARISH (down) candle before a bullish displacement (CHoCH/BOS)
- Bearish OB: last BULLISH (up) candle before a bearish displacement (CHoCH/BOS)

The displacement must be a strong impulsive move that breaks structure.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd


class OrderBlock(NamedTuple):
    kind: str  # "bullish" or "bearish"
    top: float     # OB high
    bottom: float  # OB low
    time: pd.Timestamp
    displacement_idx: int  # index of the displacement candle (CHoCH/BOS)


def detect_order_blocks(
    ohlc: pd.DataFrame,
    labels: pd.DataFrame,
    lookback: int = 5,
    min_body_pct: float = 0.3,
) -> list[OrderBlock]:
    """
    Detect Order Blocks associated with CHoCH/BOS events.

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data.
    labels : pd.DataFrame
        Output of label_structure() — must have bullish_choch, bearish_choch,
        bullish_bos, bearish_bos columns.
    lookback : int
        How many candles back to search for the last opposing candle.
    min_body_pct : float
        Minimum body-to-range ratio for the opposing candle (filters dojis).

    Returns
    -------
    list of OrderBlock
    """
    obs: list[OrderBlock] = []

    for i in range(len(ohlc)):
        row = labels.iloc[i]

        is_bullish_displacement = row["bullish_choch"] or row["bullish_bos"]
        is_bearish_displacement = row["bearish_choch"] or row["bearish_bos"]

        if not is_bullish_displacement and not is_bearish_displacement:
            continue

        # Look back for the last opposing candle
        for j in range(max(0, i - lookback), i):
            c = ohlc.iloc[j]
            body = abs(c["close"] - c["open"])
            total_range = c["high"] - c["low"]
            if total_range == 0:
                continue

            body_pct = body / total_range

            if is_bullish_displacement:
                # Bullish OB = last bearish (down) candle before the move
                if c["close"] < c["open"] and body_pct >= min_body_pct:
                    # Verify this candle is LOW enough (it's the sell-side OB)
                    obs.append(OrderBlock(
                        kind="bullish",
                        top=float(max(c["open"], c["close"])),
                        bottom=float(min(c["open"], c["close"])),
                        time=ohlc.index[j],
                        displacement_idx=i,
                    ))
                    break  # take the closest one
            elif is_bearish_displacement:
                # Bearish OB = last bullish (up) candle before the move
                if c["close"] > c["open"] and body_pct >= min_body_pct:
                    obs.append(OrderBlock(
                        kind="bearish",
                        top=float(max(c["open"], c["close"])),
                        bottom=float(min(c["open"], c["close"])),
                        time=ohlc.index[j],
                        displacement_idx=i,
                    ))
                    break

    # Deduplicate by time + displacement_idx
    seen: set[tuple] = set()
    unique: list[OrderBlock] = []
    for ob in obs:
        key = (ob.time, ob.displacement_idx)
        if key not in seen:
            seen.add(key)
            unique.append(ob)

    return unique
