"""Tests for RegimeGate wrapper (backtesting/engine/regime_gate.py).

Uses a mock inner strategy to verify delegation and filtering logic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.engine.regime import RegimeConfig
from backtesting.engine.regime_gate import RegimeGate


# ── Mock inner strategy ───────────────────────────────────────────────────

class _AlwaysSignal(Strategy):
    """Returns a fixed Signal on every next() call. Tracks call counts."""
    def __init__(self, direction: str = "long"):
        self.direction = direction
        self.init_called = False
        self.next_calls = 0
        self.close_calls = 0
        self.partial_calls = 0
        self.should_close_calls = 0

    def init(self, data: dict) -> None:
        self.init_called = True

    def next(self, bar: BarData, state: EngineState) -> Signal:
        self.next_calls += 1
        if self.direction == "long":
            return Signal(
                direction=Direction.LONG, entry=100.0, sl=99.0,
                tp1=101.0, risk_pct=0.005, label="test_signal",
            )
        return Signal(
            direction=Direction.SHORT, entry=100.0, sl=101.0,
            tp1=99.0, risk_pct=0.005, label="test_signal",
        )

    def on_close(self, trade, state) -> None:
        self.close_calls += 1

    def on_partial(self, trade, state) -> None:
        self.partial_calls += 1

    def should_close(self, position, bar, state) -> bool:
        self.should_close_calls += 1
        return False


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_data(n: int = 200, drift: float = 0.02, seed: int = 42) -> dict[str, pd.DataFrame]:
    """Build a synthetic data dict with entry TF '60'."""
    rng = np.random.default_rng(seed)
    steps = drift + rng.normal(0, 0.3, n)
    close = 100.0 + np.cumsum(steps)
    close = np.maximum(close, 1.0)
    ts = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "ts": ts, "open": close, "high": close * 1.002, "low": close * 0.998,
        "close": close, "volume": np.full(n, 1000.0),
    })
    return {"60": df}


def _make_bar(index: int, close: float = 105.0) -> BarData:
    return BarData(
        ts=pd.Timestamp("2026-01-10 00:00", tz="UTC"),
        open_=close, high=close * 1.001, low=close * 0.999,
        close=close, volume=1000.0, index=index,
    )


def _make_state(bar_index: int = 0) -> EngineState:
    return EngineState(
        equity=1000.0, initial_equity=1000.0,
        open_positions=[], closed_trades=[], bar_index=bar_index,
    )


# ── Tests ─────────────────────────────────────────────────────────────────


class TestRegimeGateWiring:
    def test_forward_signal_in_allowed_regime(self):
        """Trending bar with default allowed → signal passes through."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner)
        data = _make_data(n=400, drift=0.05, seed=10)
        gate.init(data)

        # Late bar (well past warmup) in an uptrend — should be trend_up
        signal = gate.next(_make_bar(index=300), _make_state())
        assert signal is not None
        assert signal.label == "test_signal"

    def test_suppress_signal_in_disallowed_regime(self):
        """Crypto never trades in ranging regime with defaults."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner, allowed_regimes={"trend_up", "trend_down"})
        # Random walk (drift=0) — most bars will be ranging
        data = _make_data(n=300, drift=0.0, seed=50)
        gate.init(data)

        # All bars should be checked — regime filter applies
        passed = 0
        total = 0
        for i in range(50, 250):
            s = gate.next(_make_bar(index=i), _make_state())
            total += 1
            if s is not None:
                passed += 1
        # With drift=0 and high noise, most bars should be ranging (suppressed)
        # But some may still be volatile/trend_up — just check it suppresses SOME
        assert passed < total, "Regime gate should suppress at least some signals"

    def test_custom_allowed_regime(self):
        """ranging+low_vol allowed → more signals pass in random walk."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner, allowed_regimes={"trend_up", "trend_down", "ranging"})
        data = _make_data(n=300, drift=0.05, seed=10)
        gate.init(data)

        n_passed = 0
        for i in range(50, 250):
            s = gate.next(_make_bar(index=i), _make_state())
            if s is not None:
                n_passed += 1
        # With ranging + trending allowed, most bars should pass
        assert n_passed > 100, f"Too few signals with wide allowed: {n_passed}"

    def test_empty_allowed_suppresses_all(self):
        """Empty allowed set → all signals suppressed."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner, allowed_regimes=set())
        data = _make_data(n=200, drift=0.05, seed=10)
        gate.init(data)

        for i in range(50, 150):
            assert gate.next(_make_bar(index=i), _make_state()) is None


class TestRegimeGateDelegation:
    def test_init_delegated(self):
        """inner.init() was called."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner)
        data = _make_data(n=200)
        gate.init(data)
        assert inner.init_called

    def test_on_close_delegated(self):
        inner = _AlwaysSignal()
        gate = RegimeGate(inner)
        data = _make_data(n=200)
        gate.init(data)
        gate.on_close("dummy_trade", _make_state())
        assert inner.close_calls == 1

    def test_on_partial_delegated(self):
        inner = _AlwaysSignal()
        gate = RegimeGate(inner)
        data = _make_data(n=200)
        gate.init(data)
        gate.on_partial("dummy_trade", _make_state())
        assert inner.partial_calls == 1

    def test_should_close_delegated(self):
        inner = _AlwaysSignal()
        gate = RegimeGate(inner)
        data = _make_data(n=200)
        gate.init(data)
        gate.should_close("dummy_pos", _make_bar(index=50), _make_state())
        assert inner.should_close_calls == 1

    def test_signal_source_forwarded(self):
        inner = _AlwaysSignal()
        inner._signal_source = "init_precomputed"
        gate = RegimeGate(inner)
        assert gate._signal_source == "init_precomputed"

    def test_default_signal_source(self):
        inner = _AlwaysSignal()
        gate = RegimeGate(inner)
        assert gate._signal_source == "next"


class TestRegimeGateEdgeCases:
    def test_insufficient_data_initial_bars(self):
        """Early bars with insufficient_data are suppressed."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner)
        data = _make_data(n=50, drift=0.05, seed=10)
        gate.init(data)
        # Bar 5 is before any warmup completes → insufficient_data → suppressed
        signal = gate.next(_make_bar(index=5), _make_state())
        assert signal is None, "Early bars should be suppressed"

    def test_index_out_of_bounds(self):
        """bar.index beyond labels array → signal suppressed."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner)
        data = _make_data(n=100, drift=0.05)
        gate.init(data)
        # index 200 > len(labels) = 100
        signal = gate.next(_make_bar(index=200), _make_state())
        assert signal is None

    def test_labels_not_computed(self):
        """If init() not called, labels is None → signal suppressed."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner)
        # Don't call init()
        signal = gate.next(_make_bar(index=50), _make_state())
        assert signal is None


def _make_cross_tf_data(n_entry: int = 400, n_regime: int = 100, seed: int = 10):
    """Entry TF '60' (hourly) + regime TF '240' (4-hourly), same underlying
    drift so both series describe the same trend, but at very different
    bar counts -- the exact shape that exposed the alignment bug (a 4x
    ratio here, a 414x ratio for 5m-vs-240m in real crypto data)."""
    rng = np.random.default_rng(seed)
    close_60 = 100.0 + np.cumsum(rng.normal(0.02, 0.3, n_entry))
    close_60 = np.maximum(close_60, 1.0)
    ts_60 = pd.date_range("2026-01-01", periods=n_entry, freq="1h", tz="UTC")
    df_60 = pd.DataFrame({"ts": ts_60, "open": close_60, "high": close_60 * 1.002,
                          "low": close_60 * 0.998, "close": close_60, "volume": 1000.0})

    rng2 = np.random.default_rng(seed)
    close_240 = 100.0 + np.cumsum(rng2.normal(0.02, 0.3, n_regime))
    close_240 = np.maximum(close_240, 1.0)
    ts_240 = pd.date_range("2026-01-01", periods=n_regime, freq="4h", tz="UTC")
    df_240 = pd.DataFrame({"ts": ts_240, "open": close_240, "high": close_240 * 1.002,
                           "low": close_240 * 0.998, "close": close_240, "volume": 1000.0})
    return {"60": df_60, "240": df_240}


class TestRegimeGateDifferentTF:
    def test_regime_tf_different_from_entry(self):
        """Can specify a different TF key for regime computation."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner, regime_tf="240", entry_tf="60")
        data = _make_cross_tf_data(n_entry=400, n_regime=100, seed=10)
        gate.init(data)
        signal = gate.next(_make_bar(index=300), _make_state())
        assert signal is None or signal.label == "test_signal"

    def test_labels_length_matches_entry_tf_not_regime_tf(self):
        """Bug fix regression: label array must be as long as the ENTRY
        series (400 hourly bars), not the regime series (100 4h bars) --
        this is what made every bar past index ~100 silently blocked."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner, regime_tf="240", entry_tf="60")
        data = _make_cross_tf_data(n_entry=400, n_regime=100, seed=10)
        gate.init(data)
        assert len(gate._labels) == 400

    def test_late_entry_bar_not_silently_blocked_by_short_regime_array(self):
        """Before the fix: bar.index=300 > len(regime_labels)=100 meant
        every bar past ~100 was unconditionally suppressed regardless of
        real regime. After the fix, late bars still get a real regime
        label (not just 'insufficient_data' from running off the end)."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner, regime_tf="240", entry_tf="60",
                           allowed_regimes={"trend_up", "trend_down", "ranging", "volatile", "low_vol"})
        data = _make_cross_tf_data(n_entry=400, n_regime=100, seed=10)
        gate.init(data)
        # With all real regimes allowed, a late bar should pass -- it would
        # NOT have, pre-fix, because bar.index (300) >= old label length (100).
        signal = gate.next(_make_bar(index=300), _make_state())
        assert signal is not None

    def test_alignment_uses_most_recent_regime_bar_not_same_position(self):
        """The regime label for entry bar i must come from whichever 240m
        bar was most recently CLOSED by that entry bar's timestamp (ffill
        by real time), not from regime_labels[i] at the same integer
        position -- those refer to completely different points in time
        when the two series have different bar counts."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner, regime_tf="240", entry_tf="60",
                           allowed_regimes={"trend_up", "trend_down", "ranging", "volatile", "low_vol"})
        data = _make_cross_tf_data(n_entry=400, n_regime=100, seed=10)
        gate.init(data)
        # Entry bar 40 (hour 40, i.e. 2026-01-02 16:00) should carry the
        # regime of the 240m bar covering that timestamp (240m bar index
        # 40*60/240 = 10), NOT regime_labels_raw[40] (which would be a
        # bar ~6.7 days later in the 240m series -- out of range here).
        from backtesting.engine.regime import MarketRegime
        raw_labels, _ = MarketRegime().compute(data["240"])
        assert gate._labels[40] == raw_labels[10]

    def test_nonexistent_regime_tf_fallback(self):
        """If regime_tf key is missing, falls back to first data key."""
        inner = _AlwaysSignal()
        gate = RegimeGate(inner, regime_tf="999")
        data = _make_data(n=200, drift=0.05)
        gate.init(data)  # should not crash — fallback to first key
        signal = gate.next(_make_bar(index=100), _make_state())
        assert signal is not None
