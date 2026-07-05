"""
RegimeGate — wraps any Strategy, filtering entries by market regime.

Delegates all lifecycle hooks to the inner strategy. Pre-computes regime
labels in ``init()`` (causal, safe), then suppresses ``next()`` signals
when the current bar's regime is outside the allowed set.

Usage:
    from backtesting.engine.regime import MarketRegime, RegimeConfig
    from backtesting.engine.regime_gate import RegimeGate

    gate = RegimeGate(
        inner=CryptoTsmomBreakout(risk_pct=0.005),
        allowed_regimes={"trend_up", "trend_down"},
        regime_tf="240", entry_tf="5",
    )
    result = run(gate, data, entry_tf="5", costs=costs)

Cross-timeframe alignment (fixed 2026-07-06): when ``regime_tf`` differs
from the entry timeframe (the common case -- regime is usually computed
on a slower HTF like 240m while entries fire on 5m/15m), the regime
label array is FAR shorter than the entry-bar array (e.g. 90d of 240m
bars is ~540 rows vs ~25,920 rows of 5m bars in the same window). The
original implementation indexed the short regime array directly by the
entry loop's ``bar.index``, which is wrong on two counts: (1) once
``bar.index`` exceeds the regime array's length, every subsequent bar in
the entire run silently gets no regime label and is treated as blocked
regardless of the real market state (this alone made a 90-day sweep
mostly no-op past the first ~4-5 days); (2) even within range, entry-bar
position ``i`` does not correspond to regime-bar position ``i`` at all --
they're different timeframes with different bar counts, so the labels
being read were for the wrong point in time even when in range. Fixed by
reindexing the regime-tf labels onto the entry-tf's own timestamps via
forward-fill, the same pattern already used correctly by
``CryptoFundingMeanRev`` for funding-signal alignment.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Signal
from backtesting.engine.regime import MarketRegime, RegimeConfig


# Default: trade only trending regimes — chop kills trend-following
_DEFAULT_ALLOWED = frozenset({"trend_up", "trend_down"})


class RegimeGate(Strategy):
    """Filter strategy entries by market regime.

    Wraps any ``Strategy`` subclass instance. Computes per-bar regime
    labels during ``init()`` and suppresses signals from the inner
    strategy when the entry bar's regime is not in ``allowed_regimes``.

    Attributes
    ----------
    inner : Strategy
        The wrapped strategy instance.
    allowed_regimes : set of str
        Regime labels that permit entries (default: trend_up, trend_down).
    regime_config : RegimeConfig or None
        Passed to ``MarketRegime`` for regime classification.
    regime_tf : str or None
        TF key in the ``data`` dict to compute regimes on.
        If None, uses the first key in the data dict.
    entry_tf : str or None
        TF key whose bars the entry loop actually iterates (must match
        whatever ``entry_tf`` is passed to ``engine.runner.run()``).
        Required whenever ``regime_tf`` differs from the entry timeframe
        (the common case) so regime labels can be aligned onto the
        entry bars' own timestamps. If None, falls back to the first key
        in ``data`` that isn't ``regime_tf`` -- best-effort only, pass it
        explicitly to be safe.
    """

    def __init__(
        self,
        inner: Strategy,
        allowed_regimes: Optional[set[str]] = None,
        regime_config: Optional[RegimeConfig] = None,
        regime_tf: Optional[str] = None,
        entry_tf: Optional[str] = None,
    ):
        self.inner = inner
        self.allowed_regimes = set(allowed_regimes) if allowed_regimes is not None else set(_DEFAULT_ALLOWED)
        self._config = regime_config or RegimeConfig()
        self._classifier = MarketRegime(self._config)
        self._regime_tf = regime_tf
        self._entry_tf = entry_tf
        self._labels: Optional[np.ndarray] = None

    # ── Lifecycle delegation ────────────────────────────────────────────

    def init(self, data: dict) -> None:
        """Compute regime labels, aligned onto the entry timeframe's own
        bars, then init the inner strategy.

        Regime labels are computed on ``data[self._regime_tf]`` (or the
        first available key) -- causal, no look-ahead -- then reindexed
        onto ``data[self._entry_tf]``'s timestamps via forward-fill, so
        ``self._labels[i]`` always means "the regime as of entry bar i",
        regardless of how the two timeframes' bar counts differ.
        """
        regime_tf = self._regime_tf if self._regime_tf is not None else next(iter(data.keys()))
        if regime_tf not in data:
            regime_tf = next(iter(data.keys()))  # fallback to first available
        regime_df = data[regime_tf]
        raw_labels, _ = self._classifier.compute(regime_df)

        entry_tf = self._entry_tf
        if entry_tf is None or entry_tf not in data:
            # Best-effort fallback: first key that isn't the regime tf.
            entry_tf = next((k for k in data if k != regime_tf), regime_tf)
        entry_df = data[entry_tf]

        if entry_tf == regime_tf:
            self._labels = raw_labels
        else:
            regime_ts = pd.to_datetime(regime_df["ts"], utc=True)
            entry_ts = pd.to_datetime(entry_df["ts"], utc=True)
            label_series = pd.Series(raw_labels, index=regime_ts).sort_index()
            aligned = label_series.reindex(entry_ts, method="ffill")
            self._labels = aligned.fillna("insufficient_data").to_numpy()

        # Init inner strategy
        self.inner.init(data)

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        """Get signal from inner, suppress if regime is disallowed."""
        signal = self.inner.next(bar, state)
        if signal is None:
            return None
        if self._labels is not None and bar.index < len(self._labels):
            regime = self._labels[bar.index]
            if regime in self.allowed_regimes:
                return signal
        return None

    def on_close(self, trade, state: EngineState) -> None:
        """Pass-through to inner strategy."""
        self.inner.on_close(trade, state)

    def on_partial(self, trade, state: EngineState) -> None:
        """Pass-through to inner strategy."""
        self.inner.on_partial(trade, state)

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        """Pass-through to inner strategy."""
        return self.inner.should_close(position, bar, state)

    @property
    def _signal_source(self) -> str:
        """Forward the inner strategy's signal source declaration."""
        return getattr(self.inner, "_signal_source", "next")
