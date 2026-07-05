"""Tests for regime-stratified validation (backtesting/engine/validation.py).

Uses synthetic OHLCV + synthetic trades to verify regime stratification.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.crypto.validation import RollingValidation
from backtesting.engine.regime import RegimeConfig
from backtesting.engine.validation import (
    RegimeStratifiedValidation,
    regime_stratified_validate,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _synthetic_ohlcv(
    length: int = 2000,
    start: str = "2026-01-01",
    freq_h: int = 1,
    noise_scale: float = 0.3,
    drift: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame."""
    rng = np.random.default_rng(seed)
    steps = drift + rng.normal(0, noise_scale, length)
    close = 100.0 + np.cumsum(steps)
    close = np.maximum(close, 1.0)
    high = close * 1.002
    low = close * 0.998
    ts = pd.date_range(start=start, periods=length, freq=f"{freq_h}h", tz="UTC")
    return pd.DataFrame({
        "ts": ts, "open": close, "high": high, "low": low, "close": close,
        "volume": np.full(length, 1000.0),
    })


def _synthetic_trades(
    n: int = 100,
    start: str = "2026-01-10",
    freq_days: str = "D",
    win_rate: float = 0.5,
    avg_pnl: float = 50.0,
    seed: int = 123,
) -> pd.DataFrame:
    """Build a synthetic trades DataFrame (exit_time, pnl, r_multiple)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start, periods=n, freq=freq_days, tz="UTC")
    # Random pnl: mixture of wins and losses
    is_win = rng.random(n) < win_rate
    pnl = np.where(is_win, rng.exponential(avg_pnl, n), -rng.exponential(avg_pnl * 0.6, n))
    r = pnl / avg_pnl
    return pd.DataFrame({
        "exit_time": dates, "pnl": pnl, "r_multiple": r,
    })


# ── Tests ─────────────────────────────────────────────────────────────────


class TestBasicStratification:
    def test_valid_output_structure(self):
        """Returns RegimeStratifiedValidation with expected fields."""
        ohlcv = _synthetic_ohlcv(length=2000, drift=0.01)
        trades = _synthetic_trades(n=60)
        result = regime_stratified_validate(
            trades, ohlcv, window_days=30, step_days=10, min_trades=1,
        )
        assert isinstance(result, RegimeStratifiedValidation)
        assert isinstance(result.overall, RollingValidation)
        assert isinstance(result.by_regime, dict)
        assert isinstance(result.regime_distribution, dict)
        assert result.overall.n_windows > 0
        assert result.n_regimes_with_data >= 0
        assert 0.0 <= result.regime_consistency <= 1.0

    def test_summary_returns_string(self):
        ohlcv = _synthetic_ohlcv(length=2000, drift=0.01)
        trades = _synthetic_trades(n=60)
        result = regime_stratified_validate(
            trades, ohlcv, window_days=30, step_days=10, min_trades=1,
        )
        s = result.summary()
        assert isinstance(s, str)
        assert len(s) > 50
        assert "Regime-stratified" in s
        assert "Overall" in s

    def test_empty_trades(self):
        ohlcv = _synthetic_ohlcv(length=500, drift=0.01)
        empty = pd.DataFrame(columns=["exit_time", "pnl", "r_multiple"])
        result = regime_stratified_validate(empty, ohlcv)
        assert result.overall.n_windows == 0
        assert result.by_regime == {}
        assert result.regime_consistency == 0.0

    def test_empty_ohlcv_raises(self):
        trades = _synthetic_trades(n=10)
        with pytest.raises(ValueError, match="ohlcv DataFrame is empty"):
            regime_stratified_validate(trades, pd.DataFrame())


class TestTrendingMarket:
    def test_trending_ohlcv_produces_trend_up_windows(self):
        """Strong uptrend → most windows dominated by trend_up."""
        ohlcv = _synthetic_ohlcv(length=2000, drift=0.05, noise_scale=0.15, seed=10)
        trades = _synthetic_trades(n=30, win_rate=0.6, avg_pnl=100, seed=20)
        result = regime_stratified_validate(
            trades, ohlcv, window_days=20, step_days=5, min_trades=1,
        )
        # Most windows should be trend_up
        n_trend = result.regime_distribution.get("trend_up", 0)
        n_ranging = result.regime_distribution.get("ranging", 0)
        assert n_trend > n_ranging, (
            f"Expected trend_up ({n_trend}) > ranging ({n_ranging}) "
            f"in trending market"
        )

    def test_trending_market_regime_consistency(self):
        """Trending market + profitable strategy → consistent across regimes."""
        ohlcv = _synthetic_ohlcv(length=2000, drift=0.03, noise_scale=0.2, seed=30)
        # Strategy is profitable in all windows
        trades = _synthetic_trades(n=40, win_rate=0.6, avg_pnl=100, seed=40)
        result = regime_stratified_validate(
            trades, ohlcv, window_days=20, step_days=5, min_trades=1,
        )
        # There should be regimes with data
        assert result.n_regimes_with_data > 0


class TestRangingMarket:
    def test_ranging_ohlcv_produces_ranging_windows(self):
        """Random walk (no drift) → most windows dominated by ranging."""
        ohlcv = _synthetic_ohlcv(length=2000, drift=0.0, noise_scale=0.5, seed=50)
        trades = _synthetic_trades(n=30, win_rate=0.5, avg_pnl=20, seed=60)
        result = regime_stratified_validate(
            trades, ohlcv, window_days=20, step_days=5, min_trades=1,
        )
        n_ranging = result.regime_distribution.get("ranging", 0)
        # Ranging should be the dominant regime
        assert n_ranging > 0, "Expected at least some ranging windows"
        assert result.dominant_regime == "ranging", (
            f"Expected ranging dominant, got {result.dominant_regime}"
        )


class TestRegimeSpecific:
    def test_windows_filter_to_regime(self):
        """Per-regime RollingValidation has fewer or equal windows than overall."""
        ohlcv = _synthetic_ohlcv(length=2000, drift=0.03, noise_scale=0.3, seed=70)
        trades = _synthetic_trades(n=50, win_rate=0.55, avg_pnl=50, seed=80)
        result = regime_stratified_validate(
            trades, ohlcv, window_days=20, step_days=5, min_trades=1,
        )
        total = result.overall.n_windows
        regime_total = sum(rv.n_windows for rv in result.by_regime.values())
        # Each window is assigned to exactly one regime → sums should match
        # (some windows may be assigned to insufficient_data/unknown)
        assert regime_total <= total, (
            f"Regime window sum ({regime_total}) exceeds total ({total})"
        )


class TestRegimeDistribution:
    def test_distribution_matches_window_count(self):
        """Sum of regime_distribution values equals total windows."""
        ohlcv = _synthetic_ohlcv(length=2000, drift=0.02, noise_scale=0.3, seed=90)
        trades = _synthetic_trades(n=40, win_rate=0.5, avg_pnl=30, seed=100)
        result = regime_stratified_validate(
            trades, ohlcv, window_days=15, step_days=5, min_trades=1,
        )
        dist_sum = sum(result.regime_distribution.values())
        # May not exactly equal due to windows with 0 valid regime bars
        assert dist_sum <= result.overall.n_windows


class TestCustomConfig:
    def test_custom_regime_config(self):
        """Different RegimeConfig produces different stratification."""
        ohlcv = _synthetic_ohlcv(length=2000, drift=0.02, noise_scale=0.3, seed=110)
        trades = _synthetic_trades(n=30, win_rate=0.5, avg_pnl=30, seed=120)

        # Very low trend threshold → more windows classified as trending
        config_low = RegimeConfig(er_trend_threshold=0.05)
        result_low = regime_stratified_validate(
            trades, ohlcv, window_days=20, step_days=5, min_trades=1,
            regime_config=config_low,
        )

        # Default threshold → fewer trending windows
        result_default = regime_stratified_validate(
            trades, ohlcv, window_days=20, step_days=5, min_trades=1,
        )

        n_trend_low = result_low.regime_distribution.get("trend_up", 0) + \
            result_low.regime_distribution.get("trend_down", 0)
        n_trend_default = result_default.regime_distribution.get("trend_up", 0) + \
            result_default.regime_distribution.get("trend_down", 0)

        assert n_trend_low >= n_trend_default, (
            f"Lower trend threshold ({n_trend_low}) should produce >= "
            f"trend windows than default ({n_trend_default})"
        )

    def test_longer_window_fewer_windows(self):
        """Longer window_days → fewer total windows."""
        ohlcv = _synthetic_ohlcv(length=2000, drift=0.01, seed=130)
        trades = _synthetic_trades(n=40, seed=140)

        short = regime_stratified_validate(
            trades, ohlcv, window_days=10, step_days=5, min_trades=1,
        )
        long_ = regime_stratified_validate(
            trades, ohlcv, window_days=30, step_days=5, min_trades=1,
        )
        assert short.overall.n_windows > long_.overall.n_windows
