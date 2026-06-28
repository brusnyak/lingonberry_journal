"""
Causal feature matrix from structure_lib indicators + time/session features.

Features are generated with Polars LazyFrame for performance, then converted
to NumPy for ML training. All features are CAUSAL (no look-ahead).

Feature groups:
    1. Market structure state (ict_state, direction_bias, swing structure)
    2. FVG/OB quality (gap size, age, mitigation status)
    3. Liquidity sweep (direction, reclaim, pool distance)
    4. Session/time (killzone, cyclical hour/dow)
    5. Volatility (ATR, ATR percentile, relative volume)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import polars as pl

from backtesting.engine.data import load_data
from backtesting.structure_lib.vbt_indicators import compute_all


def features_from_ohlc(
    ohlc: pd.DataFrame,
    swing_left: int = 3,
    swing_right: int = 3,
    fvg_min_gap_mult: float = 0.01,
) -> pd.DataFrame:
    """
    Build feature matrix from an in-memory OHLC DataFrame.

    Same as build_feature_matrix but uses provided data instead of loading
    from disk. Used by strategy.init() to precompute features for ML filter.

    Parameters
    ----------
    ohlc : pd.DataFrame with columns: ts, open, high, low, close
        Pre-loaded OHLC data.
    swing_left, swing_right : int
        Swing detection parameters.
    fvg_min_gap_mult : float
        Minimum FVG gap as fraction of ATR.

    Returns
    -------
    pd.DataFrame with same feature columns as build_feature_matrix.
    """
    df = ohlc.copy()
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df = df.sort_values("ts").reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    # ── Structure indicators (vbt_indicators) ───────────────────────────
    ind = compute_all(
        df, swing_left=swing_left, swing_right=swing_right,
        fvg_min_gap_atr_mult=fvg_min_gap_mult,
    )

    struct = ind["structure"]
    fvg = ind["fvg"]
    sweeps = ind["sweeps"]

    # Extract 1D arrays (single param combo)
    trend = struct.trend.values[:, 0].astype(np.int8)
    last_hh = struct.last_hh.values[:, 0]
    last_hl = struct.last_hl.values[:, 0]
    last_lh = struct.last_lh.values[:, 0]
    last_ll = struct.last_ll.values[:, 0]
    bull_bos = struct.bullish_bos.values[:, 0]
    bear_bos = struct.bearish_bos.values[:, 0]
    bull_choch = struct.bullish_choch.values[:, 0]
    bear_choch = struct.bearish_choch.values[:, 0]

    fvg_kind = fvg.kind.values[:, 0].astype(np.int8)
    fvg_top = fvg.top.values[:, 0]
    fvg_bot = fvg.bottom.values[:, 0]

    sweep_dir = sweeps.direction.values[:, 0].astype(np.int8)
    sweep_reclaim = sweeps.reclaim.values[:, 0]
    sweep_pool = sweeps.pool_level.values[:, 0]

    # ── Feature columns ──────────────────────────────────────────────────
    n = len(df)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    ts = df["ts"].to_numpy(dtype="datetime64[ns]") if "ts" in df.columns else None

    features = {}
    features["close"] = close
    features["high"] = high
    features["low"] = low

    # 1. Market structure
    features["trend"] = trend.astype(np.float64)
    features["bull_bos"] = bull_bos.astype(np.float64)
    features["bear_bos"] = bear_bos.astype(np.float64)
    features["bull_choch"] = bull_choch.astype(np.float64)
    features["bear_choch"] = bear_choch.astype(np.float64)

    # Distance to last swing points (ATR-normalized)
    atr = _atr_series(high, low, close)
    features["atr"] = atr

    features["hh_dist_atr"] = (high - last_hh) / np.maximum(atr, 1e-10)
    features["hl_dist_atr"] = (low - last_hl) / np.maximum(atr, 1e-10)
    features["lh_dist_atr"] = (high - last_lh) / np.maximum(atr, 1e-10)
    features["ll_dist_atr"] = (low - last_ll) / np.maximum(atr, 1e-10)

    # 2. FVG features
    features["fvg_kind"] = fvg_kind.astype(np.float64)
    features["fvg_gap_atr"] = np.full(n, np.nan)
    mask = fvg_kind != 0
    features["fvg_gap_atr"][mask] = np.abs(fvg_top[mask] - fvg_bot[mask]) / np.maximum(atr[mask], 1e-10)

    features["fvg_active"] = np.zeros(n, dtype=np.float64)
    for i in range(n):
        if fvg_kind[i] == 1:
            features["fvg_active"][i] = 1.0 if low[i] <= fvg_top[i] and close[i] >= fvg_bot[i] else 0.0
        elif fvg_kind[i] == -1:
            features["fvg_active"][i] = 1.0 if high[i] >= fvg_bot[i] and close[i] <= fvg_top[i] else 0.0

    # 3. Liquidity sweep features
    features["sweep_dir"] = sweep_dir.astype(np.float64)
    features["sweep_reclaim"] = sweep_reclaim.astype(np.float64)
    features["pool_dist_atr"] = np.abs(close - sweep_pool) / np.maximum(atr, 1e-10)

    # 4. Session/time features
    if ts is not None:
        hours = pd.Series(ts).dt.hour.values
        dow = pd.Series(ts).dt.dayofweek.values
        features["hour_sin"] = np.sin(2 * np.pi * hours / 24)
        features["hour_cos"] = np.cos(2 * np.pi * hours / 24)
        features["dow_sin"] = np.sin(2 * np.pi * dow / 7)
        features["dow_cos"] = np.cos(2 * np.pi * dow / 7)
        features["asia"] = ((hours >= 0) & (hours < 7)).astype(float)
        features["london_open"] = ((hours >= 7) & (hours < 10)).astype(float)
        features["ny_open"] = ((hours >= 13) & (hours < 16)).astype(float)
        features["london_ny_overlap"] = ((hours >= 12) & (hours < 16)).astype(float)
    else:
        for k in ("hour_sin", "hour_cos", "dow_sin", "dow_cos",
                  "asia", "london_open", "ny_open", "london_ny_overlap"):
            features[k] = np.zeros(n)

    # 5. Volatility
    features["atr_pctile"] = _rolling_percentile(atr, window=100)
    vol = high - low
    rel_vol = vol / (pd.Series(vol).rolling(20, min_periods=5).mean().values + 1e-10)
    features["rel_volume"] = rel_vol
    features["range_atr"] = vol / np.maximum(atr, 1e-10)

    # ── Assemble DataFrame ──────────────────────────────────────────────
    feat_df = pd.DataFrame(features)
    feat_df = feat_df.replace([np.inf, -np.inf], np.nan)
    feat_df = feat_df.ffill().fillna(0.0)
    feat_df["open"] = df["open"].values
    if ts is not None:
        feat_df["ts"] = ts

    return feat_df


def build_feature_matrix(
    symbol: str,
    tf: str = "5",
    days: int = 120,
    swing_left: int = 3,
    swing_right: int = 3,
    fvg_min_gap_mult: float = 0.01,
    include_polars: bool = True,
) -> pd.DataFrame:
    """
    Build a causal feature matrix for ML training.

    Returns DataFrame with n_bars rows, each row is a feature vector.
    All features are computable at bar close (no future data).

    Parameters
    ----------
    symbol : str
        Forex symbol (e.g. "GBPAUD").
    tf : str
        Timeframe in minutes (e.g. "5" for 5m).
    days : int
        Lookback window.
    swing_left, swing_right : int
        Swing detection parameters.
    fvg_min_gap_mult : float
        Minimum FVG gap as fraction of ATR.
    include_polars : bool
        If True, build Polars-based features (faster).

    Returns
    -------
    pd.DataFrame with columns:
        [price-based] open, high, low, close
        [structure] trend, direction_bias, hh_dist, hl_dist, lh_dist, ll_dist
        [fvg] fvg_kind, fvg_gap_atr, fvg_mitigated
        [sweep] sweep_dir, sweep_reclaim, pool_dist_atr
        [session] killzone, hour_sin, hour_cos, dow_sin, dow_cos
        [volatility] atr, atr_pctile, rel_volume
    """
    # ── Load data ───────────────────────────────────────────────────────
    ohlc = load_data(symbol, tf, days=days)
    if ohlc.empty:
        raise ValueError(f"No data for {symbol} {tf} {days}d")

    return features_from_ohlc(ohlc, swing_left, swing_right, fvg_min_gap_mult)


# ── Helpers ──────────────────────────────────────────────────────────────────────


def _atr_series(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Compute ATR series."""
    n = len(close)
    atr = np.full(n, np.nan)
    if n < 2:
        return atr
    tr = np.zeros(n)
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i - 1])
        lc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hc, lc)
    atr[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = atr[i - 1] * (1 - alpha) + tr[i] * alpha
    return atr


def _rolling_percentile(series: np.ndarray, window: int = 100) -> np.ndarray:
    """Rolling percentile rank (0-1)."""
    n = len(series)
    out = np.full(n, 0.5)
    for i in range(window, n):
        window_vals = series[i - window : i]
        valid = window_vals[np.isfinite(window_vals)]
        if len(valid) == 0:
            continue
        out[i] = np.sum(series[i] >= valid) / len(valid)
    return out


# ── Quick diagnostic ─────────────────────────────────────────────────────────────


def feature_summary(feat_df: pd.DataFrame) -> pd.DataFrame:
    """Return column-level stats for feature matrix."""
    rows = []
    for col in feat_df.select_dtypes(include=[np.number]).columns:
        s = feat_df[col]
        rows.append({
            "feature": col,
            "dtype": s.dtype,
            "n_nan": int(s.isna().sum()),
            "mean": s.mean(),
            "std": s.std(),
            "min": s.min(),
            "max": s.max(),
        })
    return pd.DataFrame(rows).sort_values("n_nan", ascending=False)


if __name__ == "__main__":
    # Quick test
    feat = build_feature_matrix("GBPAUD", "5", days=30)
    print(f"Feature matrix: {feat.shape}")
    print(feature_summary(feat).to_string(index=False))
