"""Tests for crypto pair correlation module (backtesting/engine/correlation.py).

Uses monkeypatch on ``load_data`` to inject synthetic OHLCV. Real-data
tests are in ``test_with_real_data`` at the bottom (skipped if data missing).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.engine.correlation import (
    CorrelationConfig,
    CorrelationMatrix,
    CorrelationResult,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _synthetic_ohlcv(
    length: int = 1000,
    start: str = "2026-01-01",
    freq_hours: int = 1,
    noise_scale: float = 0.0,
    drift: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame with a controlled drift + noise."""
    rng = np.random.default_rng(seed)
    steps = drift + rng.normal(0, noise_scale, length)
    close = 100.0 + np.cumsum(steps)
    close = np.maximum(close, 1.0)  # floor at 1
    high = close * 1.002
    low = close * 0.998
    ts = pd.date_range(start=start, periods=length, freq=f"{freq_hours}h", tz="UTC")
    return pd.DataFrame({
        "ts": ts, "open": close, "high": high, "low": low, "close": close,
        "volume": np.full(length, 1000.0),
    })


def _mock_load_data(ohlcv_map: dict[str, pd.DataFrame]):
    """Return a ``load_data`` replacement that looks up a pre-built map."""
    def load_data(pair: str, **kwargs) -> pd.DataFrame:
        return ohlcv_map.get(pair, pd.DataFrame()).copy()
    return load_data


# ── Tests ─────────────────────────────────────────────────────────────────


class TestBasicCorrelation:
    def test_identical_series_perfect_correlation(self, monkeypatch):
        """Two identical price series → correlation = 1.0."""
        df = _synthetic_ohlcv(length=800, noise_scale=0.5, drift=0.01)
        mock = _mock_load_data({"BTCUSDT": df, "ETHUSDT": df.copy()})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(
            tf="60", lookback_bars=500, min_bars=50,
        ))
        result = engine.compute(["BTCUSDT", "ETHUSDT"])
        r = result.matrix.loc["BTCUSDT", "ETHUSDT"]
        assert abs(r - 1.0) < 1e-6, f"Expected 1.0, got {r}"

    def test_inverse_series_negative_correlation(self, monkeypatch):
        """Inverse price series → correlation = -1.0."""
        df_a = _synthetic_ohlcv(length=800, noise_scale=0.5, drift=0.01, seed=1)
        # Build inversely correlated series
        close_a = df_a["close"].values
        close_b = 200.0 - close_a + 100.0  # inverted
        close_b = np.maximum(close_b, 1.0)
        df_b = df_a.copy()
        df_b["close"] = close_b
        df_b["high"] = close_b * 1.002
        df_b["low"] = close_b * 0.998

        mock = _mock_load_data({"BTCUSDT": df_a, "ETHUSDT": df_b})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(
            tf="60", lookback_bars=500, min_bars=50,
        ))
        result = engine.compute(["BTCUSDT", "ETHUSDT"])
        r = result.matrix.loc["BTCUSDT", "ETHUSDT"]
        assert r < -0.8, f"Expected strong negative, got {r}"

    def test_independent_series_low_correlation(self, monkeypatch):
        """Independent random walks → correlation near 0."""
        df_a = _synthetic_ohlcv(length=800, noise_scale=0.5, seed=10)
        df_b = _synthetic_ohlcv(length=800, noise_scale=0.5, seed=99)
        mock = _mock_load_data({"BTCUSDT": df_a, "ETHUSDT": df_b})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(
            tf="60", lookback_bars=500, min_bars=50,
        ))
        result = engine.compute(["BTCUSDT", "ETHUSDT"])
        r = abs(result.matrix.loc["BTCUSDT", "ETHUSDT"])
        assert r < 0.3, f"Expected near 0, got {r}"


class TestHighCorrelationDetection:
    def test_high_corr_pair_flagged(self, monkeypatch):
        """Correlated pair above threshold → in high_corr_pairs."""
        df = _synthetic_ohlcv(length=800, noise_scale=0.3, drift=0.02)
        mock = _mock_load_data({"BTCUSDT": df, "ETHUSDT": df.copy()})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(
            tf="60", lookback_bars=500, min_bars=50,
            high_corr_threshold=0.5,
        ))
        result = engine.compute(["BTCUSDT", "ETHUSDT"])
        assert len(result.high_corr_pairs) == 1
        pair_a, pair_b, r = result.high_corr_pairs[0]
        assert {pair_a, pair_b} == {"BTCUSDT", "ETHUSDT"}
        assert r > 0.5

    def test_no_high_corr_when_below_threshold(self, monkeypatch):
        """Independent series → no high_corr flags."""
        df_a = _synthetic_ohlcv(length=800, noise_scale=0.8, seed=20)
        df_b = _synthetic_ohlcv(length=800, noise_scale=0.8, seed=88)
        mock = _mock_load_data({"A": df_a, "B": df_b})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(
            tf="60", lookback_bars=500, min_bars=50,
            high_corr_threshold=0.9,
        ))
        result = engine.compute(["A", "B"])
        assert len(result.high_corr_pairs) == 0


class TestPortfolioOverlap:
    def test_single_position(self, monkeypatch):
        """Single active position → 0.0 overlap."""
        df = _synthetic_ohlcv(length=500, noise_scale=0.5)
        mock = _mock_load_data({"BTCUSDT": df})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(min_bars=50))
        result = engine.compute(["BTCUSDT"])
        overlap = engine.portfolio_overlap(["BTCUSDT"], result.matrix)
        assert overlap["mean_correlation"] == 0.0
        assert overlap["effective_count"] == 1.0
        assert overlap["missing"] == []

    def test_two_correlated_positions(self, monkeypatch):
        """Two correlated positions → high overlap, effective_count < 2."""
        df = _synthetic_ohlcv(length=800, noise_scale=0.3, drift=0.02)
        mock = _mock_load_data({"A": df, "B": df.copy()})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(
            tf="60", lookback_bars=500, min_bars=50,
        ))
        result = engine.compute(["A", "B"])
        overlap = engine.portfolio_overlap(["A", "B"], result.matrix)
        assert overlap["mean_correlation"] > 0.9
        assert overlap["effective_count"] < 1.5  # nearly 1 (one bet)

    def test_missing_pair_in_overlap(self, monkeypatch):
        """Active position not in matrix → listed in missing."""
        df = _synthetic_ohlcv(length=500, noise_scale=0.5)
        mock = _mock_load_data({"BTCUSDT": df})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(min_bars=50))
        result = engine.compute(["BTCUSDT"])
        overlap = engine.portfolio_overlap(
            ["BTCUSDT", "SOLUSDT"], result.matrix,
        )
        assert overlap["missing"] == ["SOLUSDT"]
        assert overlap["pairs"] == ["BTCUSDT"]


class TestCustomConfig:
    def test_shorter_lookback(self, monkeypatch):
        """Shorter window → still produces a valid matrix."""
        df = _synthetic_ohlcv(length=200, noise_scale=0.5)
        mock = _mock_load_data({"BTCUSDT": df, "ETHUSDT": df.copy()})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(
            tf="60", lookback_bars=50, min_bars=20,
        ))
        result = engine.compute(["BTCUSDT", "ETHUSDT"])
        assert "BTCUSDT" in result.matrix.columns
        assert result.n_bars >= 50

    def test_real_btc_vs_eth(self):
        """Smoke test with real BTCUSDT vs ETHUSDT data.

        BTC and ETH should be positively correlated (though not perfectly).
        """
        from backtesting.engine.data import load_data

        btc = load_data("BTCUSDT", tf="60", exchange="binance")
        eth = load_data("ETHUSDT", tf="60", exchange="binance")
        if btc.empty or eth.empty:
            pytest.skip("Real BTC/ETH data not available")

        # Compute manually to test the full path
        engine = CorrelationMatrix(CorrelationConfig(
            tf="60", lookback_bars=400, min_bars=50,
        ))
        result = engine.compute(["BTCUSDT", "ETHUSDT"])
        r = result.matrix.loc["BTCUSDT", "ETHUSDT"]
        assert r > 0.3, f"BTC/ETH should be positively correlated, got {r}"
        assert r < 1.0, "BTC/ETH should not be perfectly correlated"
        assert result.avg_correlation > 0
        assert len(result.high_corr_pairs) >= 1  # should flag as high corr


class TestEdgeCases:
    def test_empty_pair_list(self, monkeypatch):
        """Empty pair list → error."""
        engine = CorrelationMatrix(CorrelationConfig(min_bars=50))
        with pytest.raises(ValueError, match="No data loaded"):
            engine.compute([])

    def test_all_pairs_missing_data(self, monkeypatch):
        mock = _mock_load_data({})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)
        engine = CorrelationMatrix(CorrelationConfig(min_bars=50))
        with pytest.raises(ValueError, match="No data loaded"):
            engine.compute(["NONEXISTENT"])

    def test_single_pair(self, monkeypatch):
        """Single pair → 1×1 matrix with 1.0 on diagonal."""
        df = _synthetic_ohlcv(length=500, noise_scale=0.5)
        mock = _mock_load_data({"BTCUSDT": df})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(min_bars=50))
        result = engine.compute(["BTCUSDT"])
        assert result.matrix.shape == (1, 1)
        assert result.matrix.iloc[0, 0] == 1.0
        assert result.avg_correlation == 0.0  # no off-diagonal

    def test_output_dataclass(self, monkeypatch):
        """Result is a CorrelationResult with all fields."""
        df = _synthetic_ohlcv(length=500, noise_scale=0.5)
        mock = _mock_load_data({"A": df, "B": df.copy()})
        monkeypatch.setattr("backtesting.engine.correlation.load_data", mock)

        engine = CorrelationMatrix(CorrelationConfig(min_bars=50))
        result = engine.compute(["A", "B"])
        assert isinstance(result, CorrelationResult)
        assert hasattr(result, "matrix")
        assert hasattr(result, "returns")
        assert hasattr(result, "n_bars")
        assert hasattr(result, "pair_info")
        assert hasattr(result, "avg_correlation")
        assert hasattr(result, "high_corr_pairs")
