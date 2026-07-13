"""Tests for crypto structure cache indexing."""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.index_structure import build_one


def _bars() -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=12, freq="5min", tz="UTC")
    return pd.DataFrame({
        "ts": ts,
        "open": [1, 2, 3, 2, 1, 2, 4, 3, 2, 3, 4, 3],
        "high": [1, 2, 5, 2, 1, 2, 6, 3, 2, 4, 5, 3],
        "low": [1, 2, 3, 2, 0, 2, 4, 3, 2, 2, 3, 2],
        "close": [1, 2, 4, 2, 1, 2, 5, 3, 2, 3, 4, 2],
        "volume": [1] * 12,
    })


def test_build_one_writes_exchange_scoped_structure(monkeypatch, tmp_path):
    calls = []

    def fake_load_data(*args, **kwargs):
        calls.append((args, kwargs))
        return _bars()

    monkeypatch.setattr("backtesting.crypto.index_structure.load_data", fake_load_data)

    result = build_one(
        "BTCUSDT",
        "5",
        "binance",
        days=30,
        output_root=tmp_path,
    )

    assert result.error is None
    assert result.rows == 12
    assert result.path.exists()
    assert calls[0][1]["asset_type"] == "crypto"
    assert calls[0][1]["exchange"] == "binance"
    assert calls[0][1]["crypto_source"] == "merged"

    saved = pd.read_parquet(result.path)
    assert "known_after_ts" in saved.columns
    assert "structure_label" in saved.columns
