"""Tests for market regime classification (backtesting/engine/regime.py)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.engine.regime import (
    REGIME_LABELS,
    MarketRegime,
    RegimeConfig,
    efficiency_ratio,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_df(
    close: np.ndarray,
    base_vol_pct: float = 1.0,
    vol_spread: float = 1.6,
    seed: int = 42,
) -> pd.DataFrame:
    """Build OHLCV with varying per-bar range.

    Each bar's half-range = close * base_vol_pct/100 * (0.2 + rng * vol_spread).
    Defaults: half-range varies 0.2-1.8x of base_vol_pct.
    """
    rng = np.random.default_rng(seed)
    n = len(close)
    multiplier = 0.2 + rng.random(n) * vol_spread
    half_range = close * (base_vol_pct / 100.0) * multiplier
    high = close + half_range
    low = close - half_range
    return pd.DataFrame({"high": high, "low": low, "close": close})


def _prevalence(labels: np.ndarray, regime: str, warmup: int = 80) -> float:
    """Fraction of bars (after ``warmup``) labeled ``regime``."""
    if len(labels) <= warmup:
        return 0.0
    return float((labels[warmup:] == regime).sum()) / len(labels[warmup:])


# ── Backward compatibility ────────────────────────────────────────────────


class TestEfficiencyRatio:
    def test_perfect_trend(self):
        close = np.arange(100.0, 300.0, 1.0)
        er = efficiency_ratio(close, period=10)
        assert np.allclose(er[10:], 1.0, atol=1e-6)

    def test_pure_noise(self):
        close = np.full(100, 100.0)
        close[::2] = 101.0
        close[1::2] = 99.0
        er = efficiency_ratio(close, period=10)
        assert np.nanmean(er[10:]) < 0.05

    def test_causal(self):
        close = np.arange(100.0, 300.0, 1.0)
        er = efficiency_ratio(close, period=10)
        for i in range(10, len(close)):
            assert not np.isnan(er[i]), f"ER NaN at index {i}"


# ── MarketRegime classification ───────────────────────────────────────────


class TestTrendUp:
    def test_steady_uptrend(self):
        n = 400
        close = np.arange(100.0, 100.0 + n, 1.0)
        df = _make_df(close, base_vol_pct=1.0, vol_spread=1.6, seed=1)
        labels, _ = MarketRegime().compute(df)
        assert _prevalence(labels, "trend_up") > 0.4

    def test_last_bar_trend_up(self):
        n = 400
        close = np.arange(100.0, 100.0 + n, 1.0)
        df = _make_df(close, base_vol_pct=1.0, vol_spread=1.6, seed=1)
        labels, _ = MarketRegime().compute(df)
        assert labels[-1] == "trend_up", f"Expected trend_up, got {labels[-1]!r}"


class TestTrendDown:
    def test_steady_downtrend(self):
        n = 400
        close = np.arange(500.0, 100.0, -1.0)  # stays well above zero
        df = _make_df(close, base_vol_pct=1.0, vol_spread=1.6, seed=2)
        labels, _ = MarketRegime().compute(df)
        assert _prevalence(labels, "trend_down") > 0.4

    def test_mid_window_trend_down(self):
        """Check a bar in the middle of the downtrend where vol is stable."""
        n = 400
        close = np.arange(500.0, 100.0, -1.0)
        df = _make_df(close, base_vol_pct=1.0, vol_spread=1.6, seed=2)
        labels, _ = MarketRegime().compute(df)
        # Bar 200 (well into the trend, past all warmup windows)
        assert labels[200] == "trend_down", f"Expected trend_down, got {labels[200]!r}"


class TestRanging:
    def test_random_walk(self):
        rng = np.random.default_rng(99)
        steps = rng.normal(0, 0.05, 400)
        close = 100.0 + np.cumsum(steps)
        df = _make_df(close, base_vol_pct=0.5, vol_spread=1.6, seed=3)
        labels, _ = MarketRegime().compute(df)
        ranging_frac = _prevalence(labels, "ranging")
        assert ranging_frac > 0.25, f"ranging prevalence only {ranging_frac:.2f}"

    def test_mean_reverting(self):
        rng = np.random.default_rng(77)
        t = np.linspace(0, 10 * np.pi, 400)
        close = 100.0 + np.sin(t) * 1.5 + rng.normal(0, 0.3, 400)
        df = _make_df(close, base_vol_pct=0.5, vol_spread=1.6, seed=4)
        labels, _ = MarketRegime().compute(df)
        ranging_frac = _prevalence(labels, "ranging")
        assert ranging_frac > 0.2, f"ranging prevalence only {ranging_frac:.2f}"


class TestVolatile:
    def test_high_atr_spike(self):
        n = 400
        rng = np.random.default_rng(55)
        close = np.full(n, 100.0)
        close[-30:] += rng.normal(0, 3.0, 30)

        half_range = close * 0.005
        jitter = rng.random(n) * 0.3
        high = close + half_range + jitter
        low = close - half_range - jitter * 0.5
        # Last candle: extreme range
        high[-1] = 150.0
        low[-1] = 50.0
        close[-1] = 100.0
        df = pd.DataFrame({"high": high, "low": low, "close": close})

        labels, _ = MarketRegime().compute(df)
        assert labels[-1] == "volatile", f"Expected volatile, got {labels[-1]!r}"

    def test_volatile_priority(self):
        """Volatile overrides trend classification on extreme bars."""
        n = 400
        close = np.arange(100.0, 100.0 + n, 1.0)

        rng = np.random.default_rng(66)
        half_range = close * 0.005
        jitter = rng.random(n) * 0.3
        high = close + half_range + jitter
        low = close - half_range - jitter * 0.5
        # Extreme last candle
        high[-1] = close[-1] + 40.0
        low[-1] = close[-1] - 40.0
        df = pd.DataFrame({"high": high, "low": low, "close": close})

        labels, _ = MarketRegime().compute(df)
        assert labels[-1] == "volatile", f"Expected volatile, got {labels[-1]!r}"


class TestLowVol:
    def test_compression(self):
        """Tight range after wider range -> low_vol."""
        n = 400
        rng = np.random.default_rng(88)
        close = 100.0 + rng.normal(0, 0.5, n).cumsum()
        # Last 80 bars: extreme compression
        close[-80:] = close[-81] + rng.normal(0, 0.01, 80)

        # Wider early, tight late
        high = close * 1.005 + rng.random(n) * 0.3
        low = close * 0.995 - rng.random(n) * 0.3
        high[-80:] = close[-80:] * 1.0002
        low[-80:] = close[-80:] * 0.9998
        df = pd.DataFrame({"high": high, "low": low, "close": close})

        labels, _ = MarketRegime().compute(df)
        assert labels[-1] == "low_vol", f"Expected low_vol, got {labels[-1]!r}"


class TestInsufficientData:
    def test_very_short_series(self):
        df = _make_df(np.array([100.0, 101.0, 102.0]))
        labels, _ = MarketRegime().compute(df)
        assert all(l == "insufficient_data" for l in labels)

    def test_partial_coverage(self):
        n = 400
        close = np.arange(100.0, 100.0 + n, 1.0)
        df = _make_df(close, base_vol_pct=1.0, vol_spread=1.6, seed=5)
        labels, _ = MarketRegime().compute(df)
        assert labels[0] == "insufficient_data"
        assert labels[-1] != "insufficient_data", "Last bar should be classified"


class TestFlatPrices:
    def test_all_same_close(self):
        n = 200
        close = np.full(n, 100.0)
        high = close * 1.00001
        low = close * 0.99999
        df = pd.DataFrame({"high": high, "low": low, "close": close})
        labels, _ = MarketRegime().compute(df)
        assert labels[-1] in ("ranging", "insufficient_data", "low_vol")


class TestCustomConfig:
    def test_lower_trend_threshold(self):
        n = 400
        close = np.arange(100.0, 100.0 + n, 1.0)
        df = _make_df(close, base_vol_pct=1.0, vol_spread=1.6, seed=6)

        config_default = RegimeConfig(er_trend_threshold=0.3)
        config_low = RegimeConfig(er_trend_threshold=0.05)

        labels_default, _ = MarketRegime(config_default).compute(df)
        labels_low, _ = MarketRegime(config_low).compute(df)

        n_default = int((labels_default[100:] == "trend_up").sum())
        n_low = int((labels_low[100:] == "trend_up").sum())
        assert n_low >= n_default, (
            f"Lower threshold should produce >= trend_up labels "
            f"({n_low} vs {n_default})"
        )

    def test_higher_volatile_threshold(self):
        """A stricter threshold means fewer bars labeled volatile overall."""
        n = 400
        rng = np.random.default_rng(44)
        close = np.full(n, 100.0)
        close[-40:] += rng.normal(0, 2.0, 40)
        half_range = close * 0.005
        jitter = rng.random(n) * 0.3
        high = close + half_range + jitter
        low = close - half_range - jitter * 0.5
        high[-1] = 180.0
        low[-1] = 20.0
        close[-1] = 100.0
        df = pd.DataFrame({"high": high, "low": low, "close": close})

        config_loose = RegimeConfig(volatile_atr_percentile=0.5)
        config_strict = RegimeConfig(volatile_atr_percentile=0.98)

        labels_loose, _ = MarketRegime(config_loose).compute(df)
        labels_strict, _ = MarketRegime(config_strict).compute(df)

        n_loose = int((labels_loose[80:] == "volatile").sum())
        n_strict = int((labels_strict[80:] == "volatile").sum())
        assert n_strict < n_loose, (
            f"Strict threshold ({n_strict}) should produce fewer volatile "
            f"labels than loose threshold ({n_loose})"
        )


class TestDetails:
    def test_raw_metrics(self):
        n = 200
        close = np.arange(100.0, 100.0 + n, 1.0)
        df = _make_df(close, base_vol_pct=1.0, vol_spread=1.6, seed=7)
        labels, details = MarketRegime().compute(df)

        assert "er" in details
        assert "atr_pct" in details
        assert "atr_percentile" in details
        assert len(details["er"]) == n
        assert len(details["atr_pct"]) == n
        assert len(details["atr_percentile"]) == n
        assert np.nanmean(details["er"][60:]) > 0.9


class TestLabelValidity:
    def test_all_labels_are_valid(self):
        n = 300
        rng = np.random.default_rng(33)
        close = np.arange(100.0, 100.0 + n, 1.0)
        high = close * 1.005 + rng.random(n) * 0.5
        low = close * 0.995 - rng.random(n) * 0.5
        df = pd.DataFrame({"high": high, "low": low, "close": close})
        labels, _ = MarketRegime().compute(df)
        for lbl in labels:
            assert lbl in REGIME_LABELS, f"Invalid label: {lbl!r}"

    def test_regime_labels_are_frozenset(self):
        assert isinstance(REGIME_LABELS, frozenset)
        expected = {"volatile", "low_vol", "trend_up", "trend_down",
                    "ranging", "insufficient_data"}
        assert REGIME_LABELS == expected


# ── Edge cases ────────────────────────────────────────────────────────────


class TestRollingPercentile:
    def test_correct_denominator_with_nans(self):
        """Early bars with NaN prior values correctly compute percentile."""
        from backtesting.engine._utils import rolling_percentile as _rolling_percentile

        vals = np.full(200, np.nan)
        vals[40:] = np.arange(0.1, 0.1 + 0.01 * 160, 0.01)
        pct = _rolling_percentile(vals, 60)

        # Bar 100: 60 valid priors (indices 40-99), all < vals[100]=0.7
        assert not np.isnan(pct[100]), "Should have valid percentile at 100"
        assert 0.8 < pct[100] <= 1.0, f"Expected ~1.0, got {pct[100]:.3f}"
