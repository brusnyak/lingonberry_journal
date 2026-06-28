"""Session-anchored VWAP with bands, slope, bounce detection, and z-score.

Causal by design: each bar's VWAP uses only data from session start to that bar.
No lookahead. Session resets daily at midnight UTC (standard for forex).

Output columns (appended to input DataFrame):

  vwap              — session VWAP price
  vwap_1h, vwap_1l  — +1σ / -1σ bands
  vwap_2h, vwap_2l  — +2σ / -2σ bands
  vwap_slope_1      — VWAP slope over 1 bar (price change)
  vwap_slope_5      — VWAP slope over 5 bars (~25m on 5m data)
  vwap_slope_12     — VWAP slope over 12 bars (~1h on 5m data)
  vwap_position     — (close - vwap) / vwap, how far price is from VWAP
  vwap_z_score      — z-score of close relative to VWAP (using stdev of deviations)
  vwap_band_width   — (vwap_1h - vwap_1l) / vwap, band tightness indicator
  vwap_bounce_long  — True: price was below vwap_1l last bar, closed above it this bar
  vwap_bounce_short — True: price was above vwap_1h last bar, closed below it this bar
  vwap_trend        — "up" / "down" / "flat" based on slope_12
  vwap_inside_band  — True if close is between ±1σ bands
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────

VWAP_DEFAULT_ANCHOR = "D"  # daily session reset
VWAP_PRICE = "hlc3"         # (high + low + close) / 3
VWAP_SLOPE_FLAT_THRESH = 0.0001  # below this abs slope = "flat" trend


# ── Core VWAP ─────────────────────────────────────────────────────────────────

def _typical_price(df: pd.DataFrame) -> np.ndarray:
    """(H + L + C) / 3 per bar."""
    return (df["high"].to_numpy() + df["low"].to_numpy() + df["close"].to_numpy()) / 3.0


def _session_groups(df: pd.DataFrame) -> np.ndarray:
    """Return array of session IDs (int), resetting each day (UTC)."""
    ts = df["ts"]
    if not pd.api.types.is_datetime64_any_dtype(ts):
        ts = pd.to_datetime(ts, utc=True)
    return ts.dt.date.factorize()[0]


def build_vwap_index(
    df: pd.DataFrame,
    anchor: str = VWAP_DEFAULT_ANCHOR,
) -> pd.DataFrame:
    """Append VWAP columns to OHLCV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: ts, open, high, low, close, volume.
    anchor : str
        Resample rule for VWAP anchor. "D" = daily (default).

    Returns
    -------
    pd.DataFrame with VWAP columns added.
    """
    required = {"ts", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    out = df.copy()
    n = len(out)
    tp = _typical_price(out)
    vol = out["volume"].to_numpy(dtype=float)
    close = out["close"].to_numpy(dtype=float)
    ts_arr = out["ts"]

    # Session groups
    if anchor == "D":
        session_ids = _session_groups(out)
    else:
        raise ValueError(f"Unsupported anchor: {anchor}")

    vwap = np.full(n, np.nan, dtype=float)
    vwap_1h = np.full(n, np.nan, dtype=float)
    vwap_1l = np.full(n, np.nan, dtype=float)
    vwap_2h = np.full(n, np.nan, dtype=float)
    vwap_2l = np.full(n, np.nan, dtype=float)
    vwap_z = np.full(n, np.nan, dtype=float)

    # Per session cumulative stats
    for sid in range(session_ids.max() + 1):
        mask = session_ids == sid
        idxs = np.where(mask)[0]
        if len(idxs) == 0:
            continue

        cum_pv = 0.0   # Σ(price * volume)
        cum_v = 0.0    # Σ(volume)
        cum_dev2 = 0.0 # Σ(volume * (price - vwap)²)
        vwap_prev = np.nan

        for idx_in_sess, global_idx in enumerate(idxs):
            cum_pv += tp[global_idx] * vol[global_idx]
            cum_v += vol[global_idx]
            if cum_v > 0:
                vwap_val = cum_pv / cum_v
            else:
                vwap_val = vwap_prev if not np.isnan(vwap_prev) else np.nan

            vwap[global_idx] = vwap_val
            vwap_prev = vwap_val

            # Running standard deviation of deviations from VWAP
            dev = tp[global_idx] - vwap_val
            cum_dev2 += vol[global_idx] * dev * dev
            if idx_in_sess > 0 and cum_v > 0:
                std = np.sqrt(cum_dev2 / cum_v)
            else:
                std = 0.0

            vwap_1h[global_idx] = vwap_val + std
            vwap_1l[global_idx] = vwap_val - std
            vwap_2h[global_idx] = vwap_val + 2.0 * std
            vwap_2l[global_idx] = vwap_val - 2.0 * std
            vwap_z[global_idx] = dev / std if std > 0 else 0.0

    out["vwap"] = vwap
    out["vwap_1h"] = vwap_1h
    out["vwap_1l"] = vwap_1l
    out["vwap_2h"] = vwap_2h
    out["vwap_2l"] = vwap_2l
    out["vwap_z_score"] = vwap_z

    # ── Derived features ──────────────────────────────────────────────────

    # Position: how far close is from VWAP (fraction of VWAP)
    out["vwap_position"] = (close - vwap) / np.where(vwap != 0, vwap, 1e-10)

    # Band width
    out["vwap_band_width"] = (vwap_1h - vwap_1l) / np.where(vwap != 0, vwap, 1e-10)

    # In-band flag
    out["vwap_inside_band"] = (close >= vwap_1l) & (close <= vwap_1h)

    # Slope: rolling over different windows
    for window, col in [(1, "vwap_slope_1"), (5, "vwap_slope_5"), (12, "vwap_slope_12")]:
        shifted = pd.Series(vwap).diff(window).to_numpy()
        out[col] = shifted
        out[col] = out[col].where(~np.isnan(out[col]), 0.0)

    # Trend classification based on slope_12 (roughly 1h)
    slope_12 = out["vwap_slope_12"].to_numpy()
    trend = np.full(n, "flat", dtype=object)
    trend[slope_12 > VWAP_SLOPE_FLAT_THRESH] = "up"
    trend[slope_12 < -VWAP_SLOPE_FLAT_THRESH] = "down"
    out["vwap_trend"] = trend

    # ── Bounce detection ──────────────────────────────────────────────────

    # LONG bounce: previous bar close below vwap_1l, current bar close above vwap_1l
    prev_1l = np.roll(vwap_1l, 1)
    prev_1l[0] = np.nan
    out["vwap_bounce_long"] = (
        (np.roll(close, 1) < prev_1l)
        & (close > prev_1l)
    )

    # SHORT bounce: previous bar close above vwap_1h, current bar close below vwap_1h
    prev_1h = np.roll(vwap_1h, 1)
    prev_1h[0] = np.nan
    out["vwap_bounce_short"] = (
        (np.roll(close, 1) > prev_1h)
        & (close < prev_1h)
    )

    return out
