"""VwapRev — range-gated VWAP reversion with structural management.

Thesis (the only setup with a measured pulse, +0.30R baseline):
  In a RANGE regime (ADX<20), price stretched beyond a VWAP band reverts to fair
  value. Enter on the reversion bar. Stop at structural invalidation (recent swing).
  Bank 50% at 1R, move the rest to breakeven, let it run until an adverse structure
  break (BOS = cut, or CHoCH once in profit). No fixed far TP, no inverse RR.

All features causal via FeatureCore. Exit owned by StructuralManager.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.manage import StructuralManager
from backtesting.engine.orders import Direction, Signal
from backtesting.features.core import FeatureCore


class VwapRev(Strategy):
    spaces = {
        "z_thresh": [0.8, 1.0, 1.5],
        "tp1_r": [1.0, 1.5],
        "sl_atr_mult": [1.0, 1.5, 2.0],
        "activate_r": [0.75, 1.0],
    }

    def __init__(
        self,
        risk_pct: float = 0.005,
        pip_size: float = 0.0001,
        z_thresh: float = 1.0,         # min |VWAP z-score| to call it stretched
        tp1_r: float = 1.0,            # partial target in R
        tp1_frac: float = 0.5,
        sl_atr_mult: float = 1.5,      # ATR fallback / floor for structural SL
        atr_min_mult: float = 0.5,     # reject structural SL tighter than this*ATR
        activate_r: float = 1.0,       # arm CHoCH protection after this floating R
        regime_gate: bool = True,      # only trade ADX range regime
        adx_period: int = 14,
    ):
        self.risk_pct = risk_pct
        self.pip_size = pip_size
        self.z_thresh = z_thresh
        self.tp1_r = tp1_r
        self.tp1_frac = tp1_frac
        self.sl_atr_mult = sl_atr_mult
        self.atr_min_mult = atr_min_mult
        self.activate_r = activate_r
        self.regime_gate = regime_gate
        self.adx_period = adx_period

    def init(self, data: dict) -> None:
        entry_key = next(iter(data))
        self.core = FeatureCore(data[entry_key], adx_period=self.adx_period)
        self.mgr = StructuralManager.from_core(self.core, activate_r=self.activate_r)

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None
        c = self.core
        i = bar.index
        if i < 30 or i >= c.n:
            return None
        if self.regime_gate and c.regime[i] != "range":
            return None

        atr = c.atr[i]
        if not np.isfinite(atr) or atr <= 0:
            return None

        close = c.close[i]
        z = c.vwap_z_score[i]
        long_sig = bool(c.vwap_bounce_long[i]) and z < -self.z_thresh
        short_sig = bool(c.vwap_bounce_short[i]) and z > self.z_thresh
        if not (long_sig or short_sig):
            return None

        direction = Direction.LONG if long_sig else Direction.SHORT
        min_stop = self.atr_min_mult * atr
        struct_sl = self.mgr.entry_sl(direction, close, i)

        if direction == Direction.LONG:
            atr_sl = close - self.sl_atr_mult * atr
            sl = struct_sl if (struct_sl is not None and close - struct_sl >= min_stop) else atr_sl
            stop = close - sl
            if stop <= 0:
                return None
            tp1 = close + self.tp1_r * stop
        else:
            atr_sl = close + self.sl_atr_mult * atr
            sl = struct_sl if (struct_sl is not None and struct_sl - close >= min_stop) else atr_sl
            stop = sl - close
            if stop <= 0:
                return None
            tp1 = close - self.tp1_r * stop

        return Signal(
            direction=direction, entry=close, sl=sl, tp1=tp1,
            risk_pct=self.risk_pct, tp1_frac=self.tp1_frac, tp2_frac=0.0,
            trail=False,  # BE-after-TP1 + structural runner = let winners run
            label="vwap_rev",
        )

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        return self.mgr.should_exit(position, bar, bar.index)
