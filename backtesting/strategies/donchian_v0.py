"""
Donchian breakout v0 — the baseline to beat. Not a finished edge.

Hypothesis: price closing above the prior N-bar high (or below the prior
N-bar low) signals a breakout worth following on FX. ATR-sized stop, fixed
reward-multiple target.

Why this is the baseline:
  - Zero structure-detection / fractal-pivot lookahead. The channel is built
    from STRICTLY PRIOR bars (rolling(N).max().shift(1)), so bar i never sees
    its own high/low or anything after it.
  - Three parameters only (lookback, atr_mult, rr). At >=20 trades/param that
    needs ~60 trades to not be overfit.
  - It is the canonical thing every FX trend/breakout edge gets measured
    against. If a fancier strategy can't beat this, the fancier strategy is noise.

Run it with next_bar_fill=True (decide on close[i], fill at open[i+1]).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


class DonchianV0(Strategy):
    def __init__(
        self,
        lookback: int = 20,
        atr_mult: float = 1.5,
        rr: float = 1.5,
        atr_period: int = 14,
        risk_pct: float = 0.005,
        entry_tf: str = "15",
    ) -> None:
        self.lookback = lookback
        self.atr_mult = atr_mult
        self.rr = rr
        self.atr_period = atr_period
        self.risk_pct = risk_pct
        self.entry_tf = entry_tf

    def init(self, data: dict[str, pd.DataFrame]) -> None:
        df = data[self.entry_tf]
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Prior-bar channel: max/min over the N bars ENDING AT i-1.
        # .shift(1) is what makes it causal — bar i is compared to a channel
        # that does not include bar i itself.
        self.prior_high = high.rolling(self.lookback).max().shift(1).to_numpy()
        self.prior_low = low.rolling(self.lookback).min().shift(1).to_numpy()

        # ATR (Wilder-style simple mean of True Range over atr_period).
        prev_close = close.shift(1)
        tr = pd.concat(
            [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
            axis=1,
        ).max(axis=1)
        self.atr = tr.rolling(self.atr_period).mean().to_numpy()

        self.close = close.to_numpy()
        self._warmup = max(self.lookback, self.atr_period) + 1

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if i < self._warmup or state.has_open_position:
            return None

        atr = self.atr[i]
        ph = self.prior_high[i]
        pl = self.prior_low[i]
        if not np.isfinite(atr) or atr <= 0 or not np.isfinite(ph) or not np.isfinite(pl):
            return None

        close = self.close[i]
        sl_dist = self.atr_mult * atr
        tp_dist = self.rr * sl_dist

        if close > ph:
            return Signal(
                direction=Direction.LONG,
                entry=close,
                sl=close - sl_dist,
                tp1=close + tp_dist,
                risk_pct=self.risk_pct,
                tp1_frac=1.0,   # no partials — single clean exit for the baseline
                trail=False,
                label="donchian_long",
            )
        if close < pl:
            return Signal(
                direction=Direction.SHORT,
                entry=close,
                sl=close + sl_dist,
                tp1=close - tp_dist,
                risk_pct=self.risk_pct,
                tp1_frac=1.0,
                trail=False,
                label="donchian_short",
            )
        return None
