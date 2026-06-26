"""
Mean Reversion V2 — GBPAUD 5m

Entry logic:
  LONG  when close < sma * (1 - entry_band)  (price dipped below SMA by buffer)
  SHORT when close > sma * (1 + entry_band)  (price spiked above SMA by buffer)

Exit:
  TP:  SMA ± mean_buffer  (mean-revert back to SMA)
  SL:  entry ± stop_loss_pct  (hard percentage stop)
  No trailing, no partial (tp1_frac=1.0)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


class MeanRevV2(Strategy):
    """
    Mean reversion against SMA with configurable bands.

    Parameters
    ----------
    sma_period      : SMA lookback period (default 20)
    entry_band      : fractional distance below/above SMA to trigger (default 0.0003)
    stop_loss_pct   : fraction of entry price for hard stop (default 0.003)
    mean_buffer     : small buffer added/subtracted from SMA for TP (default 0.0002)
    long_only       : if True, only take LONG entries (default False)
    risk_pct        : risk fraction per trade (default 0.005)
    """

    def __init__(
        self,
        sma_period: int = 20,
        entry_band: float = 0.0003,
        stop_loss_pct: float = 0.003,
        mean_buffer: float = 0.0002,
        long_only: bool = False,
        risk_pct: float = 0.005,
    ) -> None:
        super().__init__()
        self.sma_period = sma_period
        self.entry_band = entry_band
        self.stop_loss_pct = stop_loss_pct
        self.mean_buffer = mean_buffer
        self.long_only = long_only
        self.risk_pct = risk_pct

    def init(self, data: dict[str, pd.DataFrame]) -> None:
        df = data["5"]
        self.sma = df["close"].rolling(self.sma_period).mean().to_numpy()
        self.close = df["close"].to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if i < self.sma_period:
            return None

        if state.has_open_position:
            return None

        sma = self.sma[i]
        close = self.close[i]

        if np.isnan(sma):
            return None

        lower_band = sma * (1.0 - self.entry_band)
        upper_band = sma * (1.0 + self.entry_band)

        if close < lower_band:
            # LONG: price dipped below SMA, expect mean reversion up
            entry = close
            sl = entry * (1.0 - self.stop_loss_pct)
            tp1 = sma + self.mean_buffer
            if tp1 <= entry:
                # SMA already below entry (shouldn't happen but guard it)
                return None
            return Signal(
                direction=Direction.LONG,
                entry=entry,
                sl=sl,
                tp1=tp1,
                tp2=999.0,   # unreachable
                tp2_frac=0.0,
                risk_pct=self.risk_pct,
                tp1_frac=1.0,
                trail=False,
                label=f"mr_long_sma{self.sma_period}",
            )

        if not self.long_only and close > upper_band:
            # SHORT: price spiked above SMA, expect mean reversion down
            entry = close
            sl = entry * (1.0 + self.stop_loss_pct)
            tp1 = sma - self.mean_buffer
            if tp1 >= entry:
                return None
            return Signal(
                direction=Direction.SHORT,
                entry=entry,
                sl=sl,
                tp1=tp1,
                tp2=0.001,   # unreachable
                tp2_frac=0.0,
                risk_pct=self.risk_pct,
                tp1_frac=1.0,
                trail=False,
                label=f"mr_short_sma{self.sma_period}",
            )

        return None
