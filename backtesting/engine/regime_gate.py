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
    )
    result = run(gate, data, entry_tf="60", costs=costs)
"""
from __future__ import annotations

from typing import Optional

import numpy as np

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
    """

    def __init__(
        self,
        inner: Strategy,
        allowed_regimes: Optional[set[str]] = None,
        regime_config: Optional[RegimeConfig] = None,
        regime_tf: Optional[str] = None,
    ):
        self.inner = inner
        self.allowed_regimes = set(allowed_regimes) if allowed_regimes is not None else set(_DEFAULT_ALLOWED)
        self._config = regime_config or RegimeConfig()
        self._classifier = MarketRegime(self._config)
        self._regime_tf = regime_tf
        self._labels: Optional[np.ndarray] = None

    # ── Lifecycle delegation ────────────────────────────────────────────

    def init(self, data: dict) -> None:
        """Compute regime labels, then init the inner strategy.

        Regime labels are pre-computed on ``data[self._regime_tf]`` (or
        the first available key). The computation is causal (rolling
        windows from ``MarketRegime``) — no look-ahead.
        """
        # Pick the TF to compute regimes on
        tf = self._regime_tf if self._regime_tf is not None else next(iter(data.keys()))
        if tf not in data:
            tf = next(iter(data.keys()))  # fallback to first available
        df = data[tf]
        self._labels, _ = self._classifier.compute(df)

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
