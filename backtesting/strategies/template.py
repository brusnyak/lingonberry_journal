"""
Strategy template — copy this, rename the class, fill in next().

To run:
    from backtesting.engine.runner import run
    from backtesting.engine.data import load_data
    from backtesting.engine.costs import ForexCosts
    from backtesting.strategies.template import ExampleStrategy

    data = {
        "1":   load_data("EURUSD", tf="1",   days=30),
        "15":  load_data("EURUSD", tf="15",  days=30),
        "240": load_data("EURUSD", tf="240", days=30),
    }
    result = run(ExampleStrategy(), data, entry_tf="1", costs=ForexCosts())
    print(result.summary())
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal


class ExampleStrategy(Strategy):
    """
    Minimal working strategy: long when 1m close > 20-bar SMA, short below.

    Replace this logic with your own. The structure here shows exactly
    what init() and next() need to do.
    """

    def init(self, data: dict[str, pd.DataFrame]) -> None:
        df = data["1"]
        self.sma = df["close"].rolling(20).mean().to_numpy()
        self.close = df["close"].to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if i < 20:
            return None

        # One trade at a time
        if state.has_open_position:
            return None

        sma = self.sma[i]
        close = self.close[i]
        atr = _atr(self.close, i, period=14)
        if atr == 0:
            return None

        sl_dist = 1.5 * atr
        tp_dist = 2.5 * atr

        if close > sma:
            return Signal(
                direction=Direction.LONG,
                entry=close,
                sl=close - sl_dist,
                tp1=close + tp_dist,
                risk_pct=0.005,
                label="sma_cross_long",
            )
        elif close < sma:
            return Signal(
                direction=Direction.SHORT,
                entry=close,
                sl=close + sl_dist,
                tp1=close - tp_dist,
                risk_pct=0.005,
                label="sma_cross_short",
            )
        return None


def _atr(close: "np.ndarray", i: int, period: int = 14) -> float:
    import numpy as np
    if i < period:
        return 0.0
    window = close[i - period: i]
    return float(np.mean(np.abs(np.diff(window))))
