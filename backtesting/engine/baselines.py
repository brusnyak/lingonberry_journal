"""Generic random-direction null wrapper — any Strategy, same triggers/risk, coin-flip direction."""
from __future__ import annotations

import random
from typing import Optional, Type

from backtesting.engine.base import Strategy
from backtesting.engine.orders import Direction, Signal


def make_random_dir_null(strategy_cls: Type[Strategy]):
    class _RandomDirNull(strategy_cls):
        def __init__(self, *args, seed: int = 0, **kwargs):
            super().__init__(*args, **kwargs)
            self._rng = random.Random(seed)

        def next(self, bar, state) -> Optional[Signal]:
            sig = super().next(bar, state)
            if sig is None:
                return None
            entry = sig.entry
            sl_dist = abs(entry - sig.sl)
            tp_dist = abs(sig.tp1 - entry)
            if self._rng.random() < 0.5:
                return Signal(direction=Direction.LONG, entry=entry, sl=entry - sl_dist,
                              tp1=entry + tp_dist, risk_pct=sig.risk_pct,
                              tp1_frac=sig.tp1_frac, tp2_frac=sig.tp2_frac,
                              trail=sig.trail, label="null_long")
            return Signal(direction=Direction.SHORT, entry=entry, sl=entry + sl_dist,
                          tp1=entry - tp_dist, risk_pct=sig.risk_pct,
                          tp1_frac=sig.tp1_frac, tp2_frac=sig.tp2_frac,
                          trail=sig.trail, label="null_short")

    _RandomDirNull.__name__ = f"RandomDirNull_{strategy_cls.__name__}"
    return _RandomDirNull
