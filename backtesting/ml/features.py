"""
Causal feature matrix from structure_lib + price action + candle patterns.

Features are generated with NumPy/Pandas for performance. All features
are CAUSAL (computed from past data only at each bar).

Feature groups:
    1. Market structure state (ict_state, direction_bias, swing structure)
    2. FVG/OB quality (gap size, age, mitigation status)
    3. Liquidity sweep (direction, reclaim, pool distance)
    4. Session/time (killzone, cyclical hour/dow)
    5. Volatility (ATR, ATR percentile, relative volume)
    6. Price action per-bar (body%, wick ratio, pin/inside/outside bars)
    7. TA-Lib candle patterns (engulfing, hammer, doji, morning star, etc.)
    8. Window-context features (rolling structure alignment, displacement)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data
from backtesting.structure_lib.vbt_indicators import compute_all

# TA-Lib is optional — if unavailable, candle pattern features are zeros
try:
    import talib as _talib
    _HAS_TALIB = True
except ImportError:
    _HAS_TALIB = False


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

    # 6. Price action per-bar features
    open_p = df["open"].to_numpy(dtype=float)
    body = close - open_p
    body_pct = np.abs(body) / np.maximum(high - low, 1e-10)
    upper_wick = high - np.maximum(open_p, close)
    lower_wick = np.minimum(open_p, close) - low
    features["body_pct"] = body_pct
    features["upper_wick"] = upper_wick
    features["lower_wick"] = lower_wick
    # Wick ratio: upper / (upper+lower+eps) — where is the rejection?
    total_wick = upper_wick + lower_wick + 1e-10
    features["upper_wick_ratio"] = upper_wick / total_wick
    features["lower_wick_ratio"] = lower_wick / total_wick
    # Pin bar: long wick (>= 2x body) on one side, small body
    features["pin_bar"] = ((upper_wick > 2 * np.abs(body)) | (lower_wick > 2 * np.abs(body))).astype(np.float64)
    # Inside bar: high <= prev_high, low >= prev_low
    prev_high = np.concatenate([[high[0]], high[:-1]])
    prev_low = np.concatenate([[low[0]], low[:-1]])
    features["inside_bar"] = ((high <= prev_high) & (low >= prev_low)).astype(np.float64)
    # Outside bar: high > prev_high, low < prev_low
    features["outside_bar"] = ((high > prev_high) & (low < prev_low)).astype(np.float64)
    # Range expansion / contraction (1.5x / 0.5x of prev bar)
    prev_vol = np.concatenate([[vol[0]], vol[:-1]])
    features["range_expansion"] = (vol > prev_vol * 1.5).astype(np.float64)
    features["range_contraction"] = (vol < prev_vol * 0.5).astype(np.float64)
    # Consecutive contraction bars (2+ in a row — coiling)
    _consec_con = np.zeros(n, dtype=np.float64)
    for i in range(2, n):
        if features["range_contraction"][i] and features["range_contraction"][i-1]:
            _consec_con[i] = 1.0
    features["coil"] = _consec_con

    # 7. Candle patterns (TA-Lib) — vectorized, 100+ patterns available
    if _HAS_TALIB and n > 1:
        o, h, l, c, = open_p.astype(float), high.astype(float), low.astype(float), close.astype(float)
        # Core reversal patterns (most predictive for forex direction)
        cdl_funcs = {
            "cdl_engulfing":      _talib.CDLENGULFING,
            "cdl_hammer":         _talib.CDLHAMMER,
            "cdl_hanging_man":    _talib.CDLHANGINGMAN,
            "cdl_shooting_star":  _talib.CDLSHOOTINGSTAR,
            "cdl_doji":           _talib.CDLDOJI,
            "cdl_doji_dragonfly": _talib.CDLDRAGONFLYDOJI,
            "cdl_doji_gravestone":_talib.CDLGRAVESTONEDOJI,
            "cdl_harami":         _talib.CDLHARAMI,
            "cdl_piercing":       _talib.CDLPIERCING,
            "cdl_dark_cloud":     _talib.CDLDARKCLOUDCOVER,
            "cdl_morning_star":   _talib.CDLMORNINGSTAR,
            "cdl_evening_star":   _talib.CDLEVENINGSTAR,
            "cdl_three_white":    _talib.CDL3WHITESOLDIERS,
            "cdl_three_black":    _talib.CDL3BLACKCROWS,
            "cdl_marubozu":       _talib.CDLMARUBOZU,
            "cdl_spinning_top":   _talib.CDLSPINNINGTOP,
            "cdl_belt_hold":      _talib.CDLBELTHOLD,
            "cdl_takuri":         _talib.CDLTAKURI,
            "cdl_inverted_hammer":_talib.CDLINVERTEDHAMMER,
            "cdl_abandoned_baby": _talib.CDLABANDONEDBABY,
            "cdl_tristar":        _talib.CDLTRISTAR,
            "cdl_rickshaw":       _talib.CDLRICKSHAWMAN,
        }
        for name, func in cdl_funcs.items():
            raw = func(o, h, l, c)
            # Normalize to 0/1: TA-Lib returns +100/0/-100 for bullish/neutral/bearish
            features[name] = (raw / 100.0).astype(np.float64)
    else:
        # No TA-Lib: all candle features are 0
        cdl_names = [
            "cdl_engulfing", "cdl_hammer", "cdl_hanging_man", "cdl_shooting_star",
            "cdl_doji", "cdl_doji_dragonfly", "cdl_doji_gravestone",
            "cdl_harami", "cdl_piercing", "cdl_dark_cloud",
            "cdl_morning_star", "cdl_evening_star", "cdl_three_white", "cdl_three_black",
            "cdl_marubozu", "cdl_spinning_top", "cdl_belt_hold", "cdl_takuri",
            "cdl_inverted_hammer", "cdl_abandoned_baby", "cdl_tristar", "cdl_rickshaw",
        ]
        for name in cdl_names:
            features[name] = np.zeros(n)

    # 8. Window-context features (rolling structure alignment)
    # These capture the "trend state over the last N bars" — the strongest
    # discriminator from forensic analysis.
    _WIN = [5, 10, 20]
    for w in _WIN:
        # Bullish ratio over window
        _bull = bull_bos.astype(float)
        _bull_sum = pd.Series(_bull).rolling(w, min_periods=1).mean().values
        features[f"bull_bos_{w}"] = _bull_sum

        _bear = bear_bos.astype(float)
        _bear_sum = pd.Series(_bear).rolling(w, min_periods=1).mean().values
        features[f"bear_bos_{w}"] = _bear_sum

        # BOS imbalance (bullish - bearish) / (bullish + bearish + 1)
        _bos_diff = _bull_sum - _bear_sum
        _bos_total = (pd.Series(_bull).rolling(w, min_periods=1).sum().values +
                      pd.Series(_bear).rolling(w, min_periods=1).sum().values + 1)
        features[f"bos_imbalance_{w}"] = _bos_diff / _bos_total

        # Displacement (net close change ATR-normalized)
        displaced = close - pd.Series(close).shift(w).values
        features[f"displacement_{w}"] = displaced / np.maximum(atr, 1e-10)

        # Bullish bar ratio (close > open) over window
        _bull_bars = pd.Series(body > 0).rolling(w, min_periods=1).mean().values
        features[f"bull_bar_ratio_{w}"] = _bull_bars

        # Pin bar rate over window
        _pin_rate = pd.Series(features["pin_bar"]).rolling(w, min_periods=1).mean().values
        features[f"pin_rate_{w}"] = _pin_rate

        # Range contraction rate over window (coiling regime)
        _con_rate = pd.Series(features["range_contraction"]).rolling(w, min_periods=1).mean().values
        features[f"con_rate_{w}"] = _con_rate

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
        [price] open, high, low, close
        [structure] trend, bull/bear_bos/choch, hh/hl/lh/ll_dist_atr
        [fvg] fvg_kind, fvg_gap_atr, fvg_active
        [sweep] sweep_dir, sweep_reclaim, pool_dist_atr
        [session] killzone, hour_sin/cos, dow_sin/cos
        [volatility] atr, atr_pctile, rel_volume, range_atr
        [PA per-bar] body_pct, upper/lower_wick, pin_bar, inside/outside_bar,
                     range_expansion/contraction, coil
        [candle] cdl_engulfing, cdl_hammer, cdl_doji, cdl_morning_star,
                 cdl_evening_star, cdl_marubozu, cdl_spinning_top, ... (22 total)
        [window] bull_bos_{w}, bear_bos_{w}, bos_imbalance_{w},
                 displacement_{w}, bull_bar_ratio_{w}, pin_rate_{w},
                 con_rate_{w} for w in [5, 10, 20]
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
