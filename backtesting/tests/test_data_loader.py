"""Tests for multi-asset data discovery and crypto source policy."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backtesting.engine.data import list_pairs, load_data


def test_list_pairs_respects_asset_type():
    crypto = set(list_pairs("crypto"))
    forex = set(list_pairs("forex"))
    commodities = set(list_pairs("commodity"))
    indices = set(list_pairs("index"))

    assert "BTCUSDT" in crypto
    assert "EURUSD" not in crypto

    assert "EURUSD" in forex
    assert "BTCUSDT" not in forex

    assert "XAUUSD" in commodities
    assert "NAS100" not in commodities

    assert "NAS100" in indices
    assert "XAUUSD" not in indices


def test_explicit_crypto_exchange_load_is_exchange_scoped():
    raw_path = Path("data/market_data/crypto/binance/BTCUSDT5.parquet")
    assert raw_path.exists(), "Audit fixture missing: binance BTCUSDT5 parquet"

    raw = pd.read_parquet(raw_path)
    loaded = load_data("BTCUSDT", "5", asset_type="crypto", exchange="binance")

    assert len(loaded) == len(raw)
    assert loaded["ts"].min() == pd.to_datetime(raw["ts"], utc=True).min()
    assert loaded["ts"].max() == pd.to_datetime(raw["ts"], utc=True).max()


def test_crypto_merged_source_keeps_legacy_history_available():
    pure = load_data("BTCUSDT", "5", asset_type="crypto", exchange="binance")
    merged = load_data(
        "BTCUSDT",
        "5",
        asset_type="crypto",
        exchange="binance",
        crypto_source="merged",
    )

    assert len(merged) > len(pure)
    assert merged["ts"].min() < pure["ts"].min()
