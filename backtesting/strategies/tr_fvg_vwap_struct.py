"""TrFvgVwapStruct — FVG + VWAP filter, exits on HIGHER-TF structure break.

Trades use fixed 1.5R TP (same as parent). If structure_trail is enabled,
the strategy ALSO monitors higher-TF structure. When the position reaches
breakeven+ (via trailing or TP1), it switches to a structure-based exit:
hold until the higher-TF structure breaks against the trade direction.

This avoids the problem of 5m CHoCHs firing on noise — only 30m/60m
structure breaks trigger the exit, and only after the position is safe.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Signal
from backtesting.engine.orders import Direction
from backtesting.features.ict_structure import IctStructureConfig, build_ict_structure_index
from backtesting.strategies.tr_fvg_vwap import TrFvgVwap


class TrFvgVwapStruct(TrFvgVwap):
    """TrFvgVwap with optional higher-TF structure-based exit.

    Two-layer exit:
      1. Normal TP1/SL from parent (1.5R TP, ATR-based SL).
      2. Structure trail: when the position reaches 0.5R+ profit, start
         monitoring higher-TF structure. Exit on opposite-direction CHoCH
         or BOS. This lets winners run without getting stopped by noise.
    """

    def __init__(
        self,
        structure_trail: bool = True,
        structure_trail_tf: str = "30",
        struct_activate_r: float = 0.5,  # activate trail after 0.5R profit
        tp1_r: float = 1.5,
        **kwargs,
    ):
        super().__init__(tp1_r=tp1_r, **kwargs)
        self.structure_trail = structure_trail
        self.structure_trail_tf = structure_trail_tf
        self.struct_activate_r = struct_activate_r

    def init(self, data: dict) -> None:
        super().init(data)
        if not self.structure_trail:
            return

        # Load higher-TF data for structure detection
        struct_key = self.structure_trail_tf
        if struct_key not in data:
            return  # no HTF data available — fall back to fixed TP

        df = data[struct_key].copy()
        struct_df = build_ict_structure_index(df, config=IctStructureConfig(left=2, right=2))

        self._struct_ts = pd.to_datetime(df["ts"], utc=True).to_numpy(dtype="datetime64[ns]")
        self._struct_bullish_bos = struct_df["bullish_bos"].to_numpy()
        self._struct_bearish_bos = struct_df["bearish_bos"].to_numpy()
        self._struct_bullish_choch = struct_df["bullish_choch"].to_numpy()
        self._struct_bearish_choch = struct_df["bearish_choch"].to_numpy()

        # Track entry prices for positions to compute floating R
        self._struct_entry_prices: dict[int, float] = {}
        self._struct_directions: dict[int, int] = {}
        self._struct_sl: dict[int, float] = {}

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        signal = super().next(bar, state)
        if signal is not None:
            # Register the position for structure tracking (used in should_close)
            # We'll track the last signal's entry/SL for the next position
            if hasattr(self, "_struct_entry_prices"):
                pass  # registration happens via Signal
        return signal

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        """Exit position on higher-TF structure break, but only if in profit."""
        if not self.structure_trail or not hasattr(self, "_struct_ts"):
            return super().should_close(position, bar, state)

        i = bar.index

        # Map to structure TF index
        ts_ns = np.datetime64(pd.Timestamp(bar.ts).to_datetime64())
        struct_i = int(np.searchsorted(self._struct_ts, ts_ns, side="right")) - 1
        if struct_i < 0 or struct_i >= len(self._struct_bearish_choch):
            return False

        # Compute floating R: current PnL / initial risk
        dir_val = direction_value(position.direction)
        if dir_val == 0 or position.original_sl is None:
            return False

        stop_dist = abs(position.entry_price - position.original_sl)
        if stop_dist == 0:
            return False

        # Current floating profit in R
        if dir_val == 1:  # LONG
            float_r = (bar.close - position.entry_price) / stop_dist
        else:
            float_r = (position.entry_price - bar.close) / stop_dist

        # Only activate structure trail when in sufficient profit
        if float_r <= self.struct_activate_r:
            return False

        # Check structure break
        if dir_val == 1:  # LONG
            # Close on bearish structure shift
            if self._struct_bearish_choch[struct_i] or self._struct_bearish_bos[struct_i]:
                return True
        else:
            if self._struct_bullish_choch[struct_i] or self._struct_bullish_bos[struct_i]:
                return True

        return False


def direction_value(direction) -> int:
    """Extract +1/-1 from Direction enum or other types."""
    if hasattr(direction, "value"):
        return 1 if direction.value == "LONG" or direction.value == 1 else -1
    if direction == "LONG" or direction == 1:
        return 1
    if direction == "SHORT" or direction == -1:
        return -1
    return 0
