"""
StructureTrendGate — filters strategy entries to agree with the higher-
timeframe structural trend (HH/HL sequence = bullish, LH/LL = bearish, via
structure_lib.label_structure), not an indicator-based regime.

Built because TrIct (structure_lib.trade_signals' "standard ICT sequence")
has no trend filter at all -- it takes sweep+CHoCH/BOS reversal signals in
either direction regardless of the larger trend, which means it'll happily
short a bearish CHoCH inside a clear uptrend (counter-trend top-pick) with
equal weight to a genuine with-trend continuation entry. This gate enforces
the discipline: only take a signal whose direction agrees with the HTF
structural trend at that bar. A bearish CHoCH during an HTF-bullish trend
is exactly the kind of local-noise reversal that should be filtered out,
not traded.

Same reindexing pattern as RegimeGate (already debugged there for the
HTF-label-onto-LTF-bars alignment bug) -- reused rather than re-derived.

Usage:
    from backtesting.engine.structure_trend_gate import StructureTrendGate
    gate = StructureTrendGate(TrIct(...), htf_key="240", entry_tf="30")
    result = run(gate, data, entry_tf="30", costs=costs)
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Signal
from backtesting.structure_lib.swing import swing_points
from backtesting.structure_lib.labels import label_structure


class StructureTrendGate(Strategy):
    def __init__(
        self,
        inner: Strategy,
        htf_key: str,
        entry_tf: Optional[str] = None,
        swing_length: int = 3,
        use_body: bool = False,  # wick-based pivots (Williams Fractal / ICT-standard convention -- 2026-07-18
                                  # research confirmed body-only pivots are neither the classical nor ICT
                                  # convention, and our own A/B test showed body-only performing worse on
                                  # XRP/SOL; keep this False unless a specific test shows otherwise)
        allow_neutral: bool = False,
    ):
        self.inner = inner
        self.htf_key = htf_key
        self.entry_tf = entry_tf
        self.swing_length = swing_length
        self.use_body = use_body
        self.allow_neutral = allow_neutral
        self._trend: Optional[np.ndarray] = None

    def init(self, data: dict) -> None:
        htf_df = data[self.htf_key]
        swings, levels = swing_points(htf_df, swing_length=self.swing_length,
                                       causal=True, use_body=self.use_body)
        labels = label_structure(htf_df, swings, levels)
        raw_trend = labels["trend"].to_numpy()  # 'bullish' / 'bearish' / 'neutral'

        entry_tf = self.entry_tf
        entry_df = data[entry_tf] if entry_tf in data else next(iter(data.values()))

        if entry_df is htf_df:
            self._trend = raw_trend
        else:
            htf_ts = pd.to_datetime(htf_df["ts"], utc=True)
            entry_ts = pd.to_datetime(entry_df["ts"], utc=True)
            trend_series = pd.Series(raw_trend, index=htf_ts).sort_index()
            aligned = trend_series.reindex(entry_ts, method="ffill")
            self._trend = aligned.fillna("neutral").to_numpy()

        self.inner.init(data)

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        signal = self.inner.next(bar, state)
        if signal is None:
            return None
        if self._trend is None or bar.index >= len(self._trend):
            return None
        trend = self._trend[bar.index]
        direction = signal.direction.value if hasattr(signal.direction, "value") else signal.direction
        if direction == "long" and trend == "bullish":
            return signal
        if direction == "short" and trend == "bearish":
            return signal
        if trend == "neutral" and self.allow_neutral:
            return signal
        return None

    def on_close(self, trade, state: EngineState) -> None:
        self.inner.on_close(trade, state)

    def on_partial(self, trade, state: EngineState) -> None:
        self.inner.on_partial(trade, state)

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        return self.inner.should_close(position, bar, state)

    @property
    def _signal_source(self) -> str:
        return getattr(self.inner, "_signal_source", "next")
