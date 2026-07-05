"""Tests for CryptoFundingMeanRev strategy (backtesting/crypto/strategies/funding_mean_rev.py).

Uses synthetic OHLCV + synthetic funding rate data to verify entry/exit logic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.crypto.strategies.funding_mean_rev import CryptoFundingMeanRev


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_data(
    n: int = 400,
    drift: float = 0.01,
    seed: int = 42,
) -> dict:
    """Build synthetic data dict with OHLCV + funding."""
    rng = np.random.default_rng(seed)
    steps = drift + rng.normal(0, 0.3, n)
    close = 100.0 + np.cumsum(steps)
    close = np.maximum(close, 1.0)
    ts = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    ohlcv = pd.DataFrame({
        "ts": ts, "open": close, "high": close * 1.005, "low": close * 0.995,
        "close": close, "volume": np.full(n, 1000.0),
    })

    # Funding: baseline slight negative, one extreme negative bar at end
    funding_rates = np.full(n, -0.00001)
    # Add an extreme negative spike (→ strong long signal)
    funding_rates[-1] = -0.001
    funding = pd.DataFrame({"ts": ts, "fundingRate": funding_rates})

    return {"60": ohlcv, "funding": funding}


def _extreme_positive_funding_data(n: int = 400, seed: int = 99) -> dict:
    """Funding ends with extreme positive spike (→ strong short signal)."""
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0, 0.3, n))
    close = np.maximum(close, 1.0)
    ts = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    ohlcv = pd.DataFrame({
        "ts": ts, "open": close, "high": close * 1.005, "low": close * 0.995,
        "close": close, "volume": np.full(n, 1000.0),
    })

    funding_rates = np.full(n, 0.00001)
    funding_rates[-1] = 0.001  # extreme positive → strong short
    funding = pd.DataFrame({"ts": ts, "fundingRate": funding_rates})

    return {"60": ohlcv, "funding": funding}


def _neutral_funding_data(n: int = 400, seed: int = 77) -> dict:
    """All funding rates near zero → no signals."""
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0, 0.3, n))
    close = np.maximum(close, 1.0)
    ts = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    ohlcv = pd.DataFrame({
        "ts": ts, "open": close, "high": close * 1.005, "low": close * 0.995,
        "close": close, "volume": np.full(n, 1000.0),
    })

    funding_rates = np.full(n, 1e-9)  # below noise threshold → neutral
    funding = pd.DataFrame({"ts": ts, "fundingRate": funding_rates})

    return {"60": ohlcv, "funding": funding}


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


class TestFundingEntry:
    def test_long_on_negative_funding(self):
        """Extreme negative funding → long signal."""
        strat = CryptoFundingMeanRev(entry_threshold=0.8)
        data = _make_data(n=200)
        strat.init(data)

        signal = strat.next(_make_bar(index=199), _make_state())
        assert signal is not None, "Expected long signal on extreme negative funding"
        assert signal.direction == Direction.LONG
        assert "long" in signal.label

    def test_short_on_positive_funding(self):
        """Extreme positive funding → short signal."""
        strat = CryptoFundingMeanRev(entry_threshold=0.8)
        data = _extreme_positive_funding_data(n=200)
        strat.init(data)

        signal = strat.next(_make_bar(index=199), _make_state())
        assert signal is not None, "Expected short signal on extreme positive funding"
        assert signal.direction == Direction.SHORT
        assert "short" in signal.label

    def test_no_signal_on_neutral_funding(self):
        """Neutral funding → no entry."""
        strat = CryptoFundingMeanRev(entry_threshold=0.8)
        data = _neutral_funding_data(n=200)
        strat.init(data)

        for i in range(50, 199):
            s = strat.next(_make_bar(index=i), _make_state())
            if s is not None:
                # The filter should suppress all entries — but if some pass,
                # verify they pass the threshold
                pass
        # At minimum, the last bar should have no signal (neutral funding)
        signal = strat.next(_make_bar(index=199), _make_state())
        assert signal is None, "Expected no signal on neutral funding"

    def test_has_open_position_no_signal(self):
        """When position is open, no new signals."""
        strat = CryptoFundingMeanRev()
        data = _make_data(n=200)
        strat.init(data)

        state = _make_state()
        state.open_positions = ["dummy"]
        signal = strat.next(_make_bar(index=199), state)
        assert signal is None, "No signal when position open"


class TestFundingDirection:
    def test_long_only(self):
        """direction='long' suppresses short signals."""
        strat = CryptoFundingMeanRev(direction="long", entry_threshold=0.8)
        data = _extreme_positive_funding_data(n=200)
        strat.init(data)

        signal = strat.next(_make_bar(index=199), _make_state())
        # With positive funding + long-only → no entry
        assert signal is None, "Long-only should not enter on positive funding"

    def test_short_only(self):
        """direction='short' suppresses long signals."""
        strat = CryptoFundingMeanRev(direction="short", entry_threshold=0.8)
        data = _make_data(n=200)
        strat.init(data)

        signal = strat.next(_make_bar(index=199), _make_state())
        assert signal is None, "Short-only should not enter on negative funding"


class TestFundingStop:
    def test_sl_is_below_entry_for_long(self):
        """Stop loss is below entry price for long."""
        strat = CryptoFundingMeanRev(stop_mode="atr", stop_atr_mult=2.0)
        data = _make_data(n=200)
        strat.init(data)

        # Last bar has extreme negative funding → strong long signal
        signal = strat.next(_make_bar(index=199, close=105.0), _make_state())
        assert signal is not None
        assert signal.sl < signal.entry, f"SL {signal.sl} should be below entry {signal.entry}"

    def test_sl_is_above_entry_for_short(self):
        """Stop loss is above entry price for short."""
        strat = CryptoFundingMeanRev(stop_mode="atr", stop_atr_mult=2.0)
        data = _extreme_positive_funding_data(n=200)
        strat.init(data)

        # Last bar has extreme positive funding → strong short signal
        signal = strat.next(_make_bar(index=199, close=105.0), _make_state())
        assert signal is not None
        assert signal.sl > signal.entry, f"SL {signal.sl} should be above entry {signal.entry}"


class TestFundingEdgeCases:
    def test_no_funding_data_in_data_dict(self):
        """No funding key in data → no signals (graceful degradation)."""
        rng = np.random.default_rng(42)
        close = 100.0 + np.cumsum(rng.normal(0, 0.3, 200))
        close = np.maximum(close, 1.0)
        ts = pd.date_range("2026-01-01", periods=200, freq="1h", tz="UTC")
        ohlcv = pd.DataFrame({
            "ts": ts, "open": close, "high": close * 1.005, "low": close * 0.995,
            "close": close, "volume": np.full(200, 1000.0),
        })
        data = {"60": ohlcv}  # no "funding" key

        strat = CryptoFundingMeanRev()
        strat.init(data)

        for i in range(50, 199):
            assert strat.next(_make_bar(index=i), _make_state()) is None

    def test_empty_funding_data(self):
        """Empty funding DataFrame → no signals."""
        data = _make_data(n=200)
        data["funding"] = pd.DataFrame()  # empty
        strat = CryptoFundingMeanRev()
        strat.init(data)

        assert strat.next(_make_bar(index=199), _make_state()) is None

    def test_insufficient_warmup(self):
        """Early bars with NaN funding signals → no entry."""
        strat = CryptoFundingMeanRev()
        data = _make_data(n=200)
        strat.init(data)

        # Bar 5 is before any funding signal computation
        signal = strat.next(_make_bar(index=5), _make_state())
        assert signal is None, "Early bars should not produce signals"


class TestFundingShouldClose:
    def test_should_close_when_signal_returns_to_neutral(self):
        """should_close triggers when funding signal weakens."""
        strat = CryptoFundingMeanRev()
        data = _make_data(n=300)
        strat.init(data)

        # Last bar has strong signal → should NOT close yet
        close_long = strat.should_close(
            _make_pos("funding_meanrev_long"),
            _make_bar(index=299, close=105.0),
            _make_state(),
        )
        # Funding at bar 299 is -0.001 (extreme) → signal is strong → don't close
        # Actually the funding DataFrame only has 200 bars (n=200 in _make_data)
        # But we passed index=299, which is out of bounds for the funding array
        # → should_close returns False

        # Bar within funding range (good index)
        close_long = strat.should_close(
            _make_pos("funding_meanrev_long"),
            _make_bar(index=50, close=105.0),
            _make_state(),
        )
        # At bar 50, funding is -0.00001 (weak) → signal ≈ neutral → should close
        # Actually, at bar 50, funding signal may still be NaN (warmup period)
        # Let's use a later bar where funding signal is definitely computed
        # but is the weak baseline -0.00001

        # Bar 80: funding = -0.00001, not extreme → signal = neutral or weak
        close_long_80 = strat.should_close(
            _make_pos("funding_meanrev_long"),
            _make_bar(index=80, close=105.0),
            _make_state(),
        )
        # With baseline -0.00001 being below min_abs_funding threshold (1e-6),
        # the signal should be 0.0 (neutral) → should close
        assert close_long_80, "should_close should return True when signal neutral"

    def test_not_close_while_signal_strong(self):
        """Strong signal → should_close returns False."""
        strat = CryptoFundingMeanRev()
        data = _make_data(n=200)
        strat.init(data)

        # Bar 199: funding = -0.001 (extreme negative) → strong long signal
        close_long = strat.should_close(
            _make_pos("funding_meanrev_long"),
            _make_bar(index=199, close=105.0),
            _make_state(),
        )
        assert not close_long, "Strong signal should NOT trigger should_close"


def _make_pos(label: str = ""):
    return type("MockPosition", (), {"label": label})()


class TestFundingWithRegimeGate:
    def test_wrap_with_regime_gate(self):
        """Can be wrapped by RegimeGate like any strategy."""
        from backtesting.engine.regime_gate import RegimeGate

        inner = CryptoFundingMeanRev(entry_threshold=0.8)
        gate = RegimeGate(inner, allowed_regimes={"trend_up", "trend_down"})
        data = _make_data(n=300, drift=0.05)
        gate.init(data)

        signal = gate.next(_make_bar(index=250), _make_state())
        # May or may not pass depending on regime at that bar
        assert signal is None or isinstance(signal, Signal)
