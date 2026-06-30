"""
Feature extraction pipeline — batch-run patterns across symbols and timeframes.

Level 1 entry point: run a single pattern across all assets/TFs and collect
direction accuracy stats. Results populate registry metadata for research.

Usage (after literature survey):
    from backtesting.features_v2.pipeline import scan_pattern
    results = scan_pattern("doji", symbols=["GBPAUD", "EURUSD"],
                           timeframes=["M5", "M15", "H1"])
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data, list_pairs, list_tfs
from backtesting.features_v2.registry import registry


def scan_pattern(
    pattern_name: str,
    symbols: Sequence[str] | None = None,
    timeframes: Sequence[str] | None = None,
    days: int = 365,
    allow_oos: bool = False,
) -> list[dict]:
    """
    Run a single candle pattern across all requested symbols/timeframes.

    Returns list of dicts with direction accuracy at multiple horizons.
    Used to falsify weak patterns fast — same gate as hypothesis engine Level 1.

    Args:
        pattern_name: registered pattern name (e.g. "doji", "engulfing")
        symbols: list of symbols; defaults to all available forex pairs
        timeframes: list of timeframes; defaults to ["M5", "M15", "H1", "H4", "D1"]
        days: lookback period in days
        allow_oos: if True, include OOS data past the OOS wall

    Returns:
        [{symbol, tf, pattern, horizon, accuracy, n_signals, ...}, ...]
    """
    if pattern_name not in registry:
        raise KeyError(f"Unknown pattern '{pattern_name}'. "
                        f"Available: {registry.names}")

    symbols = symbols or _default_symbols()
    timeframes = timeframes or ["M5", "M15", "H1", "H4", "D1"]
    results: list[dict] = []

    for tf in timeframes:
        for sym in symbols:
            df = load_data(sym, tf, days=days, allow_oos=allow_oos)
            if df.empty or len(df) < 50:
                continue

            o = df["open"].values
            h = df["high"].values
            l = df["low"].values
            c = df["close"].values

            signals = registry.run(pattern_name, o, h, l, c)
            n_signals = int(np.sum(signals != 0))

            if n_signals < 10:
                continue

            for horizon in (1, 5, 20, 50):
                acc = _direction_accuracy(signals, c, horizon)
                results.append({
                    "symbol": sym,
                    "tf": tf,
                    "pattern": pattern_name,
                    "horizon": horizon,
                    "accuracy": round(float(acc), 4),
                    "n_signals": n_signals,
                    "n_bullish": int(np.sum(signals == 1)),
                    "n_bearish": int(np.sum(signals == -1)),
                })

    return results


def _direction_accuracy(
    signals: np.ndarray,
    close: np.ndarray,
    horizon: int,
) -> float:
    """Fraction of signals where price moved in predicted direction after horizon bars."""
    n = len(close)
    if n < horizon + 2:
        return 0.5

    correct = 0
    total = 0
    for i in range(n - horizon):
        if signals[i] == 0:
            continue
        ret = close[i + horizon] - close[i]
        correct_dir = (signals[i] > 0 and ret > 0) or (signals[i] < 0 and ret < 0)
        if correct_dir:
            correct += 1
        total += 1

    return correct / total if total > 0 else 0.5


def _default_symbols() -> list[str]:
    """All forex pairs from parquet data."""
    try:
        return list_pairs(asset_type="forex")
    except Exception:
        return ["GBPAUD", "EURUSD", "GBPUSD", "AUDUSD", "EURJPY"]
