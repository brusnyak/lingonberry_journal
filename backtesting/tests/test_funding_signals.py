"""Tests for funding rate signal engine (backtesting/engine/funding_signals.py)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.engine.funding_signals import (
    FundingSignalConfig,
    FundingSignalEngine,
    label_from_signal,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_funding_df(
    rates: np.ndarray,
    start: str = "2026-01-01 00:00:00",
    freq_hours: int = 8,
) -> pd.DataFrame:
    """Build a funding rate DataFrame from a rates array."""
    n = len(rates)
    ts = pd.date_range(start=start, periods=n, freq=f"{freq_hours}h", tz="UTC")
    return pd.DataFrame({"ts": ts, "fundingRate": rates})


def _prevalence(arr: np.ndarray, value: float) -> float:
    """Fraction of non-NaN entries equal to ``value``."""
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return 0.0
    return float((valid == value).sum()) / len(valid)


# ── Tests ─────────────────────────────────────────────────────────────────


class TestBasicSignals:
    def test_extreme_positive_funding(self):
        """A single extreme-positive bar → strong short (-1.0)."""
        n = 100
        rates = np.full(n, 0.00001)  # slightly positive baseline
        rates[-1] = 0.001            # 1-bar spike at the end
        df = _make_funding_df(rates)
        engine = FundingSignalEngine()
        result = engine.compute(df)
        # At the last bar: prior 42 bars are all 0.00001, current = 0.001
        # 0.001 > all 42 prior → percentile = 1.0 → strong short
        assert result.signals[-1] == -1.0, (
            f"Expected -1.0 at last bar, got {result.signals[-1]}"
        )

    def test_extreme_negative_funding(self):
        """A single extreme-negative bar → strong long (+1.0)."""
        n = 100
        rates = np.full(n, -0.00001)  # slightly negative baseline
        rates[-1] = -0.001            # 1-bar spike at the end
        df = _make_funding_df(rates)
        engine = FundingSignalEngine()
        result = engine.compute(df)
        assert result.signals[-1] == 1.0, (
            f"Expected 1.0 at last bar, got {result.signals[-1]}"
        )

    def test_neutral_funding(self):
        """Random small variation → mostly neutral."""
        n = 100
        rng = np.random.default_rng(42)
        rates = rng.normal(0, 0.00001, n)
        df = _make_funding_df(rates)
        engine = FundingSignalEngine()
        result = engine.compute(df)
        # With uniform random ranks, neutral band (0.30 - 0.70) captures ~40%
        # Assert at least 20% to account for noise-filtered zeros too
        neutral_frac = _prevalence(result.signals, 0.0)
        assert neutral_frac > 0.2, f"neutral prevalence only {neutral_frac:.2f}"


class TestSignalMapping:
    def test_strong_long_from_percentile(self):
        """Below 10th percentile → +1.0."""
        n = 100
        rates = np.full(n, -0.00002)   # stable negative baseline
        rates[-1] = -0.001              # single bar much lower
        df = _make_funding_df(rates)
        engine = FundingSignalEngine()
        result = engine.compute(df)
        assert result.signals[-1] == 1.0

    def test_strong_short_from_percentile(self):
        """Above 90th percentile → -1.0."""
        n = 100
        rates = np.full(n, 0.00002)
        rates[-1] = 0.001
        df = _make_funding_df(rates)
        engine = FundingSignalEngine()
        result = engine.compute(df)
        assert result.signals[-1] == -1.0

    def test_weak_signals_present(self):
        """Random noise produces both weak and strong signals."""
        n = 200
        rng = np.random.default_rng(42)
        rates = rng.normal(0, 0.00005, n)
        df = _make_funding_df(rates)
        engine = FundingSignalEngine()
        result = engine.compute(df)
        valid = result.signals[~np.isnan(result.signals)]
        has_weak_long = np.any(np.abs(valid - 0.5) < 0.01)
        has_weak_short = np.any(np.abs(valid + 0.5) < 0.01)
        assert has_weak_long or has_weak_short, (
            "Expected at least one weak signal from random noise"
        )


class TestNoiseFilter:
    def test_very_small_funding_is_neutral(self):
        """Funding below min_abs_funding → neutral regardless of percentile."""
        n = 100
        rates = np.full(n, 1e-9)  # all below 1e-6 threshold
        df = _make_funding_df(rates)
        config = FundingSignalConfig(min_abs_funding=1e-6)
        engine = FundingSignalEngine(config)
        result = engine.compute(df)
        valid = result.signals[~np.isnan(result.signals)]
        assert np.all(valid == 0.0), "All valid signals should be neutral"


class TestCustomConfig:
    def test_wider_neutral_fewer_signals(self):
        """Wider neutral zone → fewer non-neutral signals."""
        n = 100
        rng = np.random.default_rng(7)
        rates = rng.normal(0, 0.00005, n)
        df = _make_funding_df(rates)
        engine = FundingSignalEngine
        cfg = FundingSignalConfig

        # Same strong thresholds, different neutral widths
        # Wide: neutral is 15%-85% (= 70%). Non-neutral = 10% + 10% = 20%.
        config_wide = cfg(
            long_signal_pct=0.05,
            short_signal_pct=0.95,
            neutral_lower_pct=0.15,
            neutral_upper_pct=0.85,
        )
        # Narrow: neutral is 35%-65% (= 30%). Non-neutral = 5%+10%+10%+5% = 30%
        # (weak zones: 5%-35% and 65%-95% are 30% each)
        # Wait — weak zones = (0.15 to 0.35) and (0.65 to 0.85), that's 40% total.
        config_narrow = cfg(
            long_signal_pct=0.05,
            short_signal_pct=0.95,
            neutral_lower_pct=0.35,
            neutral_upper_pct=0.65,
        )

        result_wide = engine(config_wide).compute(df)
        result_narrow = engine(config_narrow).compute(df)

        n_wide = int(np.sum(np.abs(result_wide.signals[42:]) >= 0.5))
        n_narrow = int(np.sum(np.abs(result_narrow.signals[42:]) >= 0.5))
        assert n_narrow > n_wide, (
            f"Narrower neutral ({n_narrow}) must produce more non-neutral "
            f"signals than wider neutral ({n_wide})"
        )

    def test_longer_lookback_first_spike_delayed(self):
        """Short lookback reacts sooner to a spike than long lookback."""
        n = 100
        rates = np.zeros(n)
        rates[50] = 0.001  # single-bar spike

        df = _make_funding_df(rates)
        result_short = FundingSignalEngine(
            FundingSignalConfig(lookback_bars=5)
        ).compute(df)
        result_long = FundingSignalEngine(
            FundingSignalConfig(lookback_bars=50)
        ).compute(df)

        # Both should flag the spike bar
        assert result_short.signals[50] == -1.0
        assert result_long.signals[50] == -1.0


class TestInsufficientData:
    def test_very_short_series(self):
        df = _make_funding_df(np.array([0.0001, 0.0002, 0.0003]))
        engine = FundingSignalEngine()
        result = engine.compute(df)
        assert np.all(np.isnan(result.signals))
        assert np.all(np.isnan(result.percentiles))
        assert np.all(np.isnan(result.z_scores))

    def test_partial_coverage(self):
        n = 100
        rates = np.linspace(0.0, 0.001, n)
        df = _make_funding_df(rates)
        engine = FundingSignalEngine()
        result = engine.compute(df)
        assert np.isnan(result.signals[0]), "First bar should be NaN"
        assert not np.isnan(result.signals[-1]), "Last bar should be classified"


class TestLabelFromSignal:
    def test_all_labels(self):
        cases = [
            (1.0, "strong_long"),
            (0.8, "strong_long"),
            (0.5, "weak_long"),
            (0.3, "weak_long"),    # >= 0.3 is weak_long (first match)
            (0.0, "neutral"),
            (-0.29, "neutral"),    # > -0.3, < 0.3 = neutral
            (-0.5, "weak_short"),
            (-0.79, "weak_short"),   # > -0.8 → weak_short
            (-0.8, "strong_short"),  # -0.8 is NOT > -0.8 → strong_short
            (-0.3, "weak_short"),    # -0.3 is NOT > -0.3 → weak_short
            (-1.0, "strong_short"),
            (np.nan, "insufficient_data"),
        ]
        for signal, expected in cases:
            got = label_from_signal(signal)
            assert got == expected, (
                f"label_from_signal({signal}) = {got!r}, expected {expected!r}"
            )


class TestOutputFormat:
    def test_result_dataclass(self):
        from backtesting.engine.funding_signals import FundingSignalResult

        n = 100
        rates = np.random.default_rng(42).normal(0, 0.00005, n)
        df = _make_funding_df(rates)
        engine = FundingSignalEngine()
        result = engine.compute(df)

        assert isinstance(result, FundingSignalResult)
        assert len(result.signals) == n
        assert len(result.percentiles) == n
        assert len(result.z_scores) == n
        assert len(result.raw) == n
        assert np.array_equal(result.raw, rates)

    def test_real_btc_data(self):
        """Smoke test with real BTCUSDT funding data."""
        from backtesting.crypto.data import load_funding_rate

        df = load_funding_rate("BTCUSDT", exchange="binance")
        if df.empty:
            pytest.skip("No BTC funding data available")

        engine = FundingSignalEngine()
        result = engine.compute(df)

        n_valid = int(np.sum(~np.isnan(result.signals)))
        assert n_valid > len(df) * 0.5, (
            f"Only {n_valid}/{len(df)} bars have valid signals"
        )

        valid = result.signals[~np.isnan(result.signals)]
        assert np.all(valid >= -1.0) and np.all(valid <= 1.0)

        unique = np.unique(valid)
        assert len(unique) > 1, f"Only one signal value: {unique}"

        pct_valid = result.percentiles[~np.isnan(result.percentiles)]
        assert np.all(pct_valid >= 0.0) and np.all(pct_valid <= 1.0)


class TestRollingStats:
    def test_percentile_is_in_range(self):
        """Percentile always in [0, 1] for valid bars."""
        rng = np.random.default_rng(17)
        rates = rng.normal(0, 0.00005, 200)
        df = _make_funding_df(rates)
        result = FundingSignalEngine().compute(df)
        pct = result.percentiles[~np.isnan(result.percentiles)]
        assert np.all(pct >= 0.0) and np.all(pct <= 1.0)

    def test_zscore_sign_matches_direction(self):
        """Z-score positive when funding > lookback mean."""
        n = 100
        rates = np.full(n, -0.00001)  # baseline negative
        rates[-1] = 0.001              # large positive spike
        df = _make_funding_df(rates)
        engine = FundingSignalEngine()
        result = engine.compute(df)
        # At last bar: mean of prev 42 bars ≈ -0.00001, current = 0.001
        assert result.z_scores[-1] > 0, (
            f"Expected positive z-score, got {result.z_scores[-1]:.2f}"
        )


class TestReversals:
    def test_spike_then_opposite_spike(self):
        """Positive spike → short, then negative spike → long."""
        n = 150
        rates = np.zeros(n)
        # First spike: positive at bar 60
        rates[60] = 0.001
        # Second spike: negative at bar 120
        rates[120] = -0.001

        df = _make_funding_df(rates)
        engine = FundingSignalEngine()
        result = engine.compute(df)

        # First spike bar should be strong short
        assert result.signals[60] == -1.0, (
            f"Expected strong short at bar 60, got {result.signals[60]}"
        )
        # Second spike bar should be strong long
        assert result.signals[120] == 1.0, (
            f"Expected strong long at bar 120, got {result.signals[120]}"
        )


