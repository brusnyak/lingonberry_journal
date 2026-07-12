"""Tests for crypto data-quality guards."""

from __future__ import annotations

import pandas as pd
import pytest

from backtesting.crypto.batch import CryptoRunConfig, _run_one_crypto, run_crypto_sweep
from backtesting.crypto.data_quality import check_funding_coverage, require_funding_coverage
from backtesting.engine.base import Strategy


def _ohlcv(start: str, periods: int = 10, freq: str = "1h") -> pd.DataFrame:
    ts = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    return pd.DataFrame({
        "ts": ts,
        "open": [100.0] * periods,
        "high": [101.0] * periods,
        "low": [99.0] * periods,
        "close": [100.0] * periods,
        "volume": [10.0] * periods,
    })


def _funding(start: str, periods: int = 3) -> pd.DataFrame:
    ts = pd.date_range(start, periods=periods, freq="8h", tz="UTC")
    return pd.DataFrame({"ts": ts, "fundingRate": [0.0001] * periods})


def test_funding_coverage_ok_within_one_funding_interval():
    coverage = check_funding_coverage(
        _ohlcv("2026-01-01T00:00:00Z", periods=17),
        _funding("2026-01-01T00:00:00Z", periods=3),
    )

    assert coverage.ok
    assert coverage.reason is None


def test_funding_coverage_fails_when_funding_ends_too_early():
    coverage = check_funding_coverage(
        _ohlcv("2026-01-01T00:00:00Z", periods=40),
        _funding("2026-01-01T00:00:00Z", periods=2),
    )

    assert not coverage.ok
    assert coverage.reason.startswith("funding_ends_before_ohlcv")


def test_funding_coverage_fails_when_funding_starts_too_late():
    coverage = check_funding_coverage(
        _ohlcv("2026-01-01T00:00:00Z", periods=10),
        _funding("2026-01-02T00:00:00Z", periods=3),
    )

    assert not coverage.ok
    assert coverage.reason.startswith("funding_starts_after_ohlcv")


def test_require_funding_coverage_raises_clear_error():
    with pytest.raises(ValueError, match="funding coverage failed"):
        require_funding_coverage(
            _ohlcv("2026-01-01T00:00:00Z", periods=40),
            _funding("2026-01-01T00:00:00Z", periods=2),
        )


class _NoopStrategy(Strategy):
    def next(self, bar, state):
        return None


def test_crypto_batch_returns_error_on_stale_funding(monkeypatch):
    monkeypatch.setattr("backtesting.crypto.batch.load_data", lambda *a, **k: _ohlcv("2026-01-01T00:00:00Z", periods=40))
    monkeypatch.setattr("backtesting.crypto.batch.load_funding_rate", lambda *a, **k: _funding("2026-01-01T00:00:00Z", periods=2))

    row = _run_one_crypto(
        _NoopStrategy,
        CryptoRunConfig(pair="BTCUSDT", entry_tf="5", support_tfs=[]),
    )

    assert row["error"].startswith("ValueError: funding coverage failed")


def test_crypto_batch_allows_stale_funding_when_explicit(monkeypatch):
    class _FakeResult:
        report = {
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "payoff_ratio": 0.0,
            "avg_r": 0.0,
            "total_pnl": 0.0,
            "return_pct": 0.0,
            "final_equity": 20.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "avg_duration_min": 0.0,
        }

    monkeypatch.setattr("backtesting.crypto.batch.load_data", lambda *a, **k: _ohlcv("2026-01-01T00:00:00Z", periods=40))
    monkeypatch.setattr("backtesting.crypto.batch.load_funding_rate", lambda *a, **k: _funding("2026-01-01T00:00:00Z", periods=2))
    monkeypatch.setattr("backtesting.crypto.batch._load_market_specs", lambda *a, **k: {})
    monkeypatch.setattr("backtesting.crypto.batch.run", lambda *a, **k: _FakeResult())

    row = _run_one_crypto(
        _NoopStrategy,
        CryptoRunConfig(
            pair="BTCUSDT",
            entry_tf="5",
            support_tfs=[],
            allow_stale_funding=True,
        ),
    )

    assert row["error"] is None


def test_crypto_sweep_handles_all_pre_metric_errors(monkeypatch):
    monkeypatch.setattr("backtesting.crypto.batch.load_data", lambda *a, **k: _ohlcv("2026-01-01T00:00:00Z", periods=40))
    monkeypatch.setattr("backtesting.crypto.batch.load_funding_rate", lambda *a, **k: _funding("2026-01-01T00:00:00Z", periods=2))

    df = run_crypto_sweep(
        _NoopStrategy,
        [CryptoRunConfig(pair="BTCUSDT", entry_tf="5", support_tfs=[])],
        verbose=False,
    )

    assert len(df) == 1
    assert df.iloc[0]["error"].startswith("ValueError: funding coverage failed")
    assert "profit_factor" in df.columns
