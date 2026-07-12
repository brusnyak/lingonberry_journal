"""Tests for rerunnable data freshness audit."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backtesting.data_audit import audit_all, main, parse_symbol_tf


def _write_ohlcv(path: Path, start: str, periods: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = pd.date_range(start, periods=periods, freq="5min", tz="UTC")
    pd.DataFrame({
        "ts": ts,
        "open": [1.0] * periods,
        "high": [1.1] * periods,
        "low": [0.9] * periods,
        "close": [1.0] * periods,
        "volume": [100.0] * periods,
    }).to_parquet(path, index=False)


def _write_funding(path: Path, start: str, periods: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = pd.date_range(start, periods=periods, freq="8h", tz="UTC")
    pd.DataFrame({"ts": ts, "fundingRate": [0.0001] * periods}).to_parquet(path, index=False)


def test_parse_symbol_tf_preserves_digits_in_symbol():
    assert parse_symbol_tf(Path("NAS1005.parquet")) == ("NAS100", "5")
    assert parse_symbol_tf(Path("SPX5001440.parquet")) == ("SPX500", "1440")
    assert parse_symbol_tf(Path("BTCUSDT15.parquet")) == ("BTCUSDT", "15")


def test_audit_all_discovers_market_data_and_funding(tmp_path):
    _write_ohlcv(tmp_path / "market_data" / "crypto" / "binance" / "BTCUSDT5.parquet", "2026-07-01")
    _write_funding(tmp_path / "market_data" / "crypto" / "binance" / "BTCUSDT_funding.parquet", "2026-07-01")
    _write_ohlcv(tmp_path / "market_data" / "index" / "parquet" / "NAS1005.parquet", "2026-07-01")

    df = audit_all(tmp_path, as_of=pd.Timestamp("2026-07-03T00:00:00Z"))

    assert set(df["category"]) == {"ohlcv", "funding"}
    assert set(df["symbol"]) == {"BTCUSDT", "NAS100"}
    assert df[df["symbol"] == "NAS100"].iloc[0]["asset_type"] == "index"


def test_fail_on_stale_exit_code(tmp_path):
    _write_ohlcv(tmp_path / "market_data" / "forex" / "parquet" / "EURUSD5.parquet", "2026-01-01")

    code = main([
        "--data-root", str(tmp_path),
        "--as-of", "2026-07-12T00:00:00Z",
        "--max-stale-days", "7",
        "--fail-on-stale",
    ])

    assert code == 1
