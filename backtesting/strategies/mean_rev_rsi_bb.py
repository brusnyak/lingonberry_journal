"""
Mean-reversion: RSI + Bollinger Bands, ADX trend filter. (ported strategy, our engine)

A different family from the falsified breakout-follow / sweep-fade lines: this
FADES band extremes and reverts to the mean, only in non-trending regimes.

Long : RSI < os and close < lower BB   (oversold, stretched below band)
Short: RSI > ob and close > upper BB   (overbought, stretched above band)
Filter: ADX < adx_threshold            (skip strong trends — MR dies in trends)
Stop : entry ∓ atr_mult * ATR
Exit : reverts to BB mid (SMA)  OR  ADX spikes past threshold+10  (should_close)
       plus a static target snapshot at the entry-bar SMA.

All indicators vectorized causally in init() (rolling/ewm = past+present only),
indexed by bar in next(). Run with next_bar_fill=True.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


class MeanRevRsiBb(Strategy):
    def __init__(
        self,
        rsi_period: int = 14,
        rsi_os: float = 30.0,
        rsi_ob: float = 70.0,
        bb_period: int = 20,
        bb_std: float = 2.0,
        adx_period: int = 14,
        adx_threshold: float = 25.0,
        atr_period: int = 14,
        atr_mult: float = 1.5,
        risk_pct: float = 0.005,
        entry_tf: str = "15",
    ) -> None:
        self.rsi_period = rsi_period
        self.rsi_os = rsi_os
        self.rsi_ob = rsi_ob
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.risk_pct = risk_pct
        self.entry_tf = entry_tf

    def init(self, data: dict[str, pd.DataFrame]) -> None:
        df = data[self.entry_tf]
        high, low, close = df["high"], df["low"], df["close"]

        # RSI (Wilder)
        delta = close.diff()
        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)
        a = 1.0 / self.rsi_period
        avg_g = gain.ewm(alpha=a, adjust=False).mean()
        avg_l = loss.ewm(alpha=a, adjust=False).mean()
        rs = avg_g / (avg_l + 1e-12)
        self.rsi = (100.0 - 100.0 / (1.0 + rs)).to_numpy()

        # Bollinger
        sma = close.rolling(self.bb_period).mean()
        sd = close.rolling(self.bb_period).std(ddof=0)
        self.sma = sma.to_numpy()
        self.upper = (sma + self.bb_std * sd).to_numpy()
        self.lower = (sma - self.bb_std * sd).to_numpy()

        # ATR (Wilder)
        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(),
                        (low - prev_close).abs()], axis=1).max(axis=1)
        aa = 1.0 / self.atr_period
        atr = tr.ewm(alpha=aa, adjust=False).mean()
        self.atr = atr.to_numpy()

        # ADX (Wilder)
        up = high.diff()
        dn = -low.diff()
        plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
        minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
        ad = 1.0 / self.adx_period
        atr_w = tr.ewm(alpha=ad, adjust=False).mean()
        plus_di = 100.0 * pd.Series(plus_dm, index=df.index).ewm(alpha=ad, adjust=False).mean() / (atr_w + 1e-12)
        minus_di = 100.0 * pd.Series(minus_dm, index=df.index).ewm(alpha=ad, adjust=False).mean() / (atr_w + 1e-12)
        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-12)
        self.adx = dx.ewm(alpha=ad, adjust=False).mean().to_numpy()

        self.close = close.to_numpy()
        self._warmup = max(self.rsi_period, self.bb_period, self.adx_period, self.atr_period) + 5

    # ── dynamic exit: revert to mean, or trend ignites ──
    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        i = bar.index
        sma, adx = self.sma[i], self.adx[i]
        if not np.isfinite(sma):
            return False
        trend_ignite = np.isfinite(adx) and adx > self.adx_threshold + 10
        d = position.direction.value if hasattr(position.direction, "value") else position.direction
        if d == "long":
            return bar.close >= sma or trend_ignite
        return bar.close <= sma or trend_ignite

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if i < self._warmup or state.has_open_position:
            return None

        rsi, adx, atr = self.rsi[i], self.adx[i], self.atr[i]
        sma, up, lo = self.sma[i], self.upper[i], self.lower[i]
        if not all(np.isfinite(x) for x in (rsi, adx, atr, sma, up, lo)) or atr <= 0:
            return None
        if adx > self.adx_threshold:   # skip trending regime
            return None

        c = self.close[i]
        stop_dist = self.atr_mult * atr

        # Long: oversold + below lower band; target = mean (must be above entry)
        if rsi < self.rsi_os and c < lo and sma > c:
            return Signal(direction=Direction.LONG, entry=c, sl=c - stop_dist,
                          tp1=sma, risk_pct=self.risk_pct, tp1_frac=1.0,
                          trail=False, label="mr_long")
        # Short: overbought + above upper band; target = mean (must be below entry)
        if rsi > self.rsi_ob and c > up and sma < c:
            return Signal(direction=Direction.SHORT, entry=c, sl=c + stop_dist,
                          tp1=sma, risk_pct=self.risk_pct, tp1_frac=1.0,
                          trail=False, label="mr_short")
        return None
