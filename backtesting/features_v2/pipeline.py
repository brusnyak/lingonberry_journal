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
    timeframes = timeframes or [5, 15, 60, 240, 1440]
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

            pip_size = _pip_size(sym)
            cost_pips = 3.5  # round-trip: ~2 entry + ~1 exit + ~0.5 slip (costs.py)
            for horizon in (1, 5, 20, 50):
                acc, net_acc, n_resolved = _direction_accuracy(
                    signals, c, horizon, pip_size, cost_pips
                )
                results.append({
                    "symbol": sym,
                    "tf": tf,
                    "pattern": pattern_name,
                    "horizon": horizon,
                    "accuracy": round(float(acc), 4),
                    "net_accuracy": round(float(net_acc), 4),
                    "n_signals": n_signals,
                    "n_resolved": n_resolved,
                    "n_bullish": int(np.sum(signals == 1)),
                    "n_bearish": int(np.sum(signals == -1)),
                })

    return results


def _pip_size(symbol: str) -> float:
    """Forex pip size: 0.01 for JPY pairs, 0.0001 otherwise."""
    return 0.01 if "JPY" in symbol else 0.0001


def _direction_accuracy(
    signals: np.ndarray,
    close: np.ndarray,
    horizon: int,
    pip_size: float,
    cost_pips: float,
) -> tuple[float, float, int]:
    """
    Direction accuracy, raw and cost-net.

    Raw: fraction of signals where price moved in predicted direction.
    Net: same, but only counting signals whose move exceeds round-trip cost
    (cost_pips). Signals that don't clear cost are excluded from net_accuracy's
    denominator — they're "noise" trades that would lose to spread either way.
    """
    n = len(close)
    if n < horizon + 2:
        return 0.5, 0.5, 0

    cost_price = cost_pips * pip_size
    correct = 0
    total = 0
    net_correct = 0
    net_total = 0
    for i in range(n - horizon):
        if signals[i] == 0:
            continue
        ret = close[i + horizon] - close[i]
        correct_dir = (signals[i] > 0 and ret > 0) or (signals[i] < 0 and ret < 0)
        if correct_dir:
            correct += 1
        total += 1

        if abs(ret) > cost_price:
            net_total += 1
            if correct_dir:
                net_correct += 1

    acc = correct / total if total > 0 else 0.5
    net_acc = net_correct / net_total if net_total > 0 else 0.5
    return acc, net_acc, net_total


def _default_symbols() -> list[str]:
    """All forex pairs from parquet data."""
    try:
        return list_pairs(asset_type="forex")
    except Exception:
        return ["GBPAUD", "EURUSD", "GBPUSD", "AUDUSD", "EURJPY"]
