"""Causal direction and entry-quality filters for crypto research.

This layer is deliberately small. It does not try to be an ICT engine; it
answers whether a candidate entry has structure confirmation available at the
decision timestamp, and whether the recent tape contains an opposing spike that
should invalidate a naive retest entry.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DirectionLayerConfig:
    confirmation_window_bars: int = 8
    opposing_spike_lookback_bars: int = 4
    opposing_spike_atr: float = 1.75
    opposing_spike_close_frac: float = 0.25


def structure_at(structure: pd.DataFrame, decision_ts: pd.Timestamp) -> pd.Series | None:
    """Return the latest structure row known at `decision_ts`.

    The only valid timestamp for this lookup is `known_after_ts`. Pivot time is
    reference time, not availability time.
    """
    if structure is None or structure.empty or "known_after_ts" not in structure.columns:
        return None
    right = structure.copy()
    right["known_after_ts"] = pd.to_datetime(right["known_after_ts"], utc=True, errors="coerce")
    right = right.dropna(subset=["known_after_ts"])
    if right.empty:
        return None
    decision = pd.Timestamp(decision_ts).tz_convert("UTC") if pd.Timestamp(decision_ts).tzinfo else pd.Timestamp(decision_ts, tz="UTC")
    known = right[right["known_after_ts"] <= decision].sort_values("known_after_ts")
    if known.empty:
        return None
    return known.iloc[-1]


def has_direction_confirmation(
    structure: pd.DataFrame,
    *,
    direction: str,
    signal_ts: pd.Timestamp,
    entry_ts: pd.Timestamp,
    bar_delta: pd.Timedelta,
    config: DirectionLayerConfig | None = None,
) -> tuple[bool, str, pd.Timestamp | pd.NaT]:
    """Check whether structure confirms the trade direction without lookahead."""
    cfg = config or DirectionLayerConfig()
    if structure is None or structure.empty or "known_after_ts" not in structure.columns:
        return False, "missing_structure", pd.NaT

    direction = direction.lower()
    if direction not in {"long", "short"}:
        raise ValueError("direction must be long or short")

    right = structure.copy()
    right["known_after_ts"] = pd.to_datetime(right["known_after_ts"], utc=True, errors="coerce")
    right = right.dropna(subset=["known_after_ts"]).sort_values("known_after_ts")
    if right.empty:
        return False, "missing_structure", pd.NaT

    entry = _utc(entry_ts)
    signal = _utc(signal_ts)
    lookback_start = signal - max(cfg.confirmation_window_bars, 0) * bar_delta
    causal = right[right["known_after_ts"] <= entry]
    if causal.empty:
        return False, "no_known_structure", pd.NaT

    latest = causal.iloc[-1]
    regime = str(latest.get("regime", "")).lower()
    if direction == "short" and regime == "bear":
        return True, "latest_bear_regime", latest["known_after_ts"]
    if direction == "long" and regime == "bull":
        return True, "latest_bull_regime", latest["known_after_ts"]

    recent = causal[causal["known_after_ts"] >= lookback_start]
    if direction == "short":
        cols = [c for c in ["bos_down", "choch_down", "bearish_bos", "bearish_choch"] if c in recent.columns]
    else:
        cols = [c for c in ["bos_up", "choch_up", "bullish_bos", "bullish_choch"] if c in recent.columns]
    for col in cols:
        hits = recent[recent[col].astype(bool)]
        if not hits.empty:
            return True, col, hits.iloc[-1]["known_after_ts"]
    return False, "no_direction_confirmation", pd.NaT


def has_opposing_spike(
    data: pd.DataFrame,
    *,
    direction: str,
    entry_i: int,
    atr: pd.Series,
    config: DirectionLayerConfig | None = None,
) -> tuple[bool, str]:
    """Detect a recent opposing displacement/rejection before an entry."""
    cfg = config or DirectionLayerConfig()
    direction = direction.lower()
    if direction not in {"long", "short"}:
        raise ValueError("direction must be long or short")
    if entry_i <= 0 or len(data) == 0:
        return False, "none"

    start = max(0, entry_i - cfg.opposing_spike_lookback_bars)
    end = min(entry_i, len(data) - 1)
    for j in range(start, end + 1):
        atr_now = float(atr.iat[j]) if j < len(atr) and np.isfinite(atr.iat[j]) else np.nan
        if not np.isfinite(atr_now) or atr_now <= 0:
            continue
        open_ = float(data["open"].iat[j])
        high = float(data["high"].iat[j])
        low = float(data["low"].iat[j])
        close = float(data["close"].iat[j])
        candle_range = high - low
        if candle_range <= 0 or candle_range < cfg.opposing_spike_atr * atr_now:
            continue
        close_near_high = close >= high - candle_range * cfg.opposing_spike_close_frac
        close_near_low = close <= low + candle_range * cfg.opposing_spike_close_frac
        if direction == "short" and close > open_ and close_near_high:
            return True, "bullish_opposing_spike"
        if direction == "long" and close < open_ and close_near_low:
            return True, "bearish_opposing_spike"
    return False, "none"


def _utc(ts: pd.Timestamp) -> pd.Timestamp:
    out = pd.Timestamp(ts)
    if out.tzinfo is None:
        return out.tz_localize("UTC")
    return out.tz_convert("UTC")
