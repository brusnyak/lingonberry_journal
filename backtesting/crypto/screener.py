"""
Tier-2 crypto pair screener.

Scans all available USDT perp pairs, computes liquidity/volatility/history
metrics from a small data sample, and returns a ranked DataFrame.

Strategies consume the output via `screen_pairs()` or the ranked list directly.

Usage:
    from backtesting.crypto.screener import screen_pairs, rank_pairs

    df = screen_pairs(days=14, exchange="binance")
    # → DataFrame with all 24 pairs, raw metrics

    ranked = rank_pairs(df, weights={"volatility": 0.5, "volume": 0.3, "days": 0.2})
    # → same DataFrame with 'score' column, sorted descending
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data


def _compute_metrics(df: pd.DataFrame) -> dict:
    """Compute screening metrics from a OHLCV DataFrame (any timeframe)."""
    if df.empty or len(df) < 20:
        return {}

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    volume = df["volume"].values if "volume" in df.columns else np.ones(len(df))
    price = float(close[-1])

    # Daily aggregates (resample efficiently)
    _df = df.copy()
    _df["ts"] = pd.to_datetime(_df["ts"])
    daily = _df.set_index("ts").resample("D").agg({
        "high": "max", "low": "min", "close": "last", "volume": "sum",
    }).dropna()

    # — Volatility (ATR % of price over the available period) —
    tr = np.maximum(
        high - low,
        np.maximum(
            abs(np.diff(close, prepend=close[0])),
            abs(high - np.roll(close, 1)),
        ),
    )
    tr[0] = high[0] - low[0]
    atr = float(np.mean(tr))
    volatility = atr / price if price > 0 else 0.0

    # — Avg daily volume —
    avg_volume = float(daily["volume"].mean()) if len(daily) > 0 else float(np.mean(volume))

    # — Avg daily range % —
    daily_range_pct = ((daily["high"] - daily["low"]) / daily["close"]).mean()
    daily_range_pct = float(daily_range_pct) if not np.isnan(daily_range_pct) else 0.0

    # — Directional ratio (efficiency ratio) —
    total_move = abs(float(close[-1] - close[0]))
    sum_moves = float(np.sum(np.abs(np.diff(close))))
    directional_ratio = total_move / sum_moves if sum_moves > 0 else 0.0

    # — Skew (close vs mid of daily range) —
    if len(daily) > 0:
        daily_mid = (daily["high"] + daily["low"]) / 2
        skew = ((daily["close"] - daily_mid) / (daily["high"] - daily["low"] + 1e-9)).mean()
        skew = float(skew)
    else:
        skew = 0.0

    return {
        "price": round(price, 8),
        "volatility": round(volatility, 6),
        "atr": round(atr, 8),
        "avg_volume": round(avg_volume, 2),
        "avg_daily_volume": round(avg_volume, 2),
        "avg_daily_range_pct": round(daily_range_pct, 4),
        "directional_ratio": round(directional_ratio, 4),
        "skew": round(skew, 4),
        "bars": len(df),
        "days": len(daily),
    }


def screen_pairs(
    tf: str = "60",
    days: int = 14,
    exchange: Optional[str] = None,
    min_days: int = 3,
) -> pd.DataFrame:
    """
    Screen all available crypto USDT pairs and compute screening metrics.

    Parameters
    ----------
    tf : str
        Timeframe for metric computation ('60' default = fast, '30' = more bars).
    days : int
        How far back to load for each pair.
    exchange : str or None
        'binance', 'bybit', or None (both, best available).
    min_days : int
        Minimum days of data required to include pair.

    Returns
    -------
    pd.DataFrame with columns: pair, price, volatility, atr, avg_volume,
    avg_daily_range_pct, directional_ratio, skew, bars, days.
    """
    from backtesting.engine.data import list_pairs

    all_pairs = [p for p in list_pairs("crypto") if p.endswith("USDT")]
    all_pairs.sort()

    rows = []
    for symbol in all_pairs:
        try:
            df = load_data(symbol, tf=tf, days=days, exchange=exchange)
        except Exception:
            continue
        metrics = _compute_metrics(df)
        if not metrics or metrics.get("days", 0) < min_days:
            continue
        metrics["pair"] = symbol
        rows.append(metrics)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    cols = ["pair", "price", "volatility", "atr", "avg_daily_volume",
            "avg_daily_range_pct", "directional_ratio", "skew", "bars", "days"]
    result = result[[c for c in cols if c in result.columns]]
    return result.sort_values("pair").reset_index(drop=True)


def rank_pairs(
    df: pd.DataFrame,
    weights: Optional[dict[str, float]] = None,
    top_n: Optional[int] = None,
) -> pd.DataFrame:
    """
    Rank screened pairs by a weighted score.

    Default weights balance volatility + volume + ranging behavior.
    Each metric is min-max normalized before weighting.

    Parameters
    ----------
    df : pd.DataFrame
        Output from screen_pairs().
    weights : dict
        Metric → weight pairs. Unknown metrics are ignored.
        Default: {"volatility": 0.35, "avg_daily_volume": 0.35, "directional_ratio": -0.30}.
        Negative weight = penalize (e.g., too directional = bad for mean reversion).
    top_n : int or None
        Return only top N pairs.

    Returns
    -------
    pd.DataFrame with 'score' column, sorted descending.
    """
    if df.empty:
        return df

    default_weights = {
        "volatility": 0.35,
        "avg_daily_volume": 0.35,
        "directional_ratio": -0.30,
    }
    if weights is None:
        weights = default_weights

    result = df.copy()
    result["_score"] = 0.0

    for metric, w in weights.items():
        if metric not in result.columns:
            continue

        col = result[metric].values.astype(float)
        mn, mx = float(col.min()), float(col.max())
        if mx - mn < 1e-12:
            norm = np.zeros_like(col)
        else:
            norm = (col - mn) / (mx - mn)

        result["_score"] += norm * w

    # Normalize final score to [0, 1]
    scores = result["_score"].values
    mn, mx = float(scores.min()), float(scores.max())
    if mx - mn > 1e-12:
        result["score"] = (scores - mn) / (mx - mn)
    else:
        result["score"] = 0.5

    result = result.drop(columns=["_score"])
    result = result.sort_values("score", ascending=False).reset_index(drop=True)

    if top_n is not None and top_n < len(result):
        result = result.head(top_n)

    return result
