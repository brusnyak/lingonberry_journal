"""TrFvgVwap — FVG fill reversal with VWAP directional filter."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Signal
from backtesting.engine.orders import Direction
from backtesting.features.vwap import build_vwap_index
from backtesting.strategies.tr_fvg import TrFvg


class TrFvgVwap(TrFvg):
    """FVG fill reversal with VWAP-based directional filter.

    Extends TrFvg with an optional VWAP slope filter. When enabled, signals
    whose direction contradicts the VWAP 12-bar slope (approx 1h on 5m data)
    are suppressed. VWAP slope must not strongly oppose the trade direction.
    A slope below 0.5 x pip_size is treated as flat/neutral and ignored.
    """

    def __init__(
        self,
        vwap_filter: bool = True,
        sl_buffer_pips: int = 5,
        tp1_r: float = 1.5,
        tp1_frac: float = 0.6,
        risk_pct: float = 0.005,
        pip_size: float = 0.0001,
        direction: str = "bear",
        min_gap_atr_pct: float = 0.3,
        htf_momentum_bars: int = 10,
        htf_agree: bool = True,
        htf_structure: bool = False,
        htf_struct_bars: int = 3,
        killzone: bool = False,
        kz_sessions: tuple = ((7, 10), (12, 16)),
        sl_mode: str = "fixed",
        structure_sl_lookback: int = 20,
        structure_sl_swing_n: int = 3,
        ob_sl_min_stop: float = 3.0,
        ob_sl_strict: bool = False,
        regime_bars: int = 20,
    ):
        super().__init__(
            sl_buffer_pips=sl_buffer_pips,
            tp1_r=tp1_r,
            tp1_frac=tp1_frac,
            risk_pct=risk_pct,
            pip_size=pip_size,
            direction=direction,
            min_gap_atr_pct=min_gap_atr_pct,
            htf_momentum_bars=htf_momentum_bars,
            htf_agree=htf_agree,
            htf_structure=htf_structure,
            htf_struct_bars=htf_struct_bars,
            killzone=killzone,
            kz_sessions=kz_sessions,
            sl_mode=sl_mode,
            structure_sl_lookback=structure_sl_lookback,
            structure_sl_swing_n=structure_sl_swing_n,
            ob_sl_min_stop=ob_sl_min_stop,
            ob_sl_strict=ob_sl_strict,
            regime_bars=regime_bars,
        )
        self.vwap_filter = vwap_filter

    def init(self, data: dict) -> None:
        super().init(data)
        if not self.vwap_filter:
            return

        entry_key = next(iter(data))
        df = data[entry_key].copy()
        vwap_df = build_vwap_index(df)

        self._vwap = vwap_df["vwap"].to_numpy()
        self._vwap_slope_12 = vwap_df["vwap_slope_12"].to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        signal = super().next(bar, state)
        if signal is None or not self.vwap_filter:
            return signal

        i = bar.index
        if i >= len(self._vwap_slope_12):
            return signal

        slope = self._vwap_slope_12[i]

        # Treat sub-threshold slope as flat/neutral — no filter
        if abs(slope) < 0.5 * self.pip_size:
            return signal

        # VWAP falling opposes longs, VWAP rising opposes shorts
        if signal.direction == Direction.LONG and slope < 0:
            return None
        if signal.direction == Direction.SHORT and slope > 0:
            return None

        return signal
