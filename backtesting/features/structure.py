"""No-lookahead market structure feature index.

The output row at timestamp `ts` contains structure information known after
that candle closes. A strategy entering at the next candle open can safely use
the previous completed row. Confirmed pivots are emitted at their confirmation
timestamp, not at the pivot timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StructureConfig:
    left: int = 2
    right: int = 2


def build_structure_index(df: pd.DataFrame, config: StructureConfig | None = None) -> pd.DataFrame:
    """Return candle-aligned structure features for OHLCV data."""
    cfg = config or StructureConfig()
    _validate(df, cfg)

    data = df[["ts", "open", "high", "low", "close"]].copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    data = data.sort_values("ts").reset_index(drop=True)

    n = len(data)
    high = data["high"].to_numpy(dtype=float)
    low = data["low"].to_numpy(dtype=float)
    close = data["close"].to_numpy(dtype=float)
    ts = data["ts"].tolist()
    bar_delta = _infer_bar_delta(data["ts"])
    known_after = [t + bar_delta for t in ts]

    pivot_events = _confirmed_pivots(high, low, ts, cfg)

    rows = []
    last_swing_high = np.nan
    last_swing_low = np.nan
    last_swing_high_ts = pd.NaT
    last_swing_low_ts = pd.NaT
    last_hh = np.nan
    last_hl = np.nan
    last_lh = np.nan
    last_ll = np.nan
    last_hh_ts = pd.NaT
    last_hl_ts = pd.NaT
    last_lh_ts = pd.NaT
    last_ll_ts = pd.NaT
    regime = "neutral"
    broken_hh = False
    broken_ll = False
    broken_hl = False
    broken_lh = False

    events_by_confirm: dict[int, list[dict]] = {}
    for event in pivot_events:
        events_by_confirm.setdefault(event["confirm_i"], []).append(event)

    for i in range(n):
        swing_type = ""
        swing_price = np.nan
        swing_ts = pd.NaT
        structure_label = ""

        for event in events_by_confirm.get(i, []):
            swing_type = event["swing_type"]
            swing_price = event["price"]
            swing_ts = event["pivot_ts"]

            if swing_type == "high":
                if np.isnan(last_swing_high):
                    structure_label = "1H"
                elif swing_price > last_swing_high:
                    structure_label = "HH"
                    last_hh = swing_price
                    last_hh_ts = swing_ts
                    broken_hh = False
                else:
                    structure_label = "LH"
                    last_lh = swing_price
                    last_lh_ts = swing_ts
                    broken_lh = False
                last_swing_high = swing_price
                last_swing_high_ts = swing_ts

            elif swing_type == "low":
                if np.isnan(last_swing_low):
                    structure_label = "1L"
                elif swing_price > last_swing_low:
                    structure_label = "HL"
                    last_hl = swing_price
                    last_hl_ts = swing_ts
                    broken_hl = False
                else:
                    structure_label = "LL"
                    last_ll = swing_price
                    last_ll_ts = swing_ts
                    broken_ll = False
                last_swing_low = swing_price
                last_swing_low_ts = swing_ts

            if not np.isnan(last_hh) and not np.isnan(last_hl):
                regime = "bull"
            if not np.isnan(last_lh) and not np.isnan(last_ll):
                regime = "bear"

        bos_up = False
        bos_down = False
        choch_up = False
        choch_down = False
        bos_level = np.nan
        choch_level = np.nan

        if not broken_hh and not np.isnan(last_hh) and close[i] > last_hh:
            bos_up = True
            bos_level = last_hh
            broken_hh = True
            if regime == "bear":
                choch_up = True
                choch_level = last_hh
                broken_lh = True
                regime = "neutral"
            else:
                regime = "bull"

        if not broken_ll and not np.isnan(last_ll) and close[i] < last_ll:
            bos_down = True
            bos_level = last_ll
            broken_ll = True
            if regime == "bull":
                choch_down = True
                choch_level = last_ll
                broken_hl = True
                regime = "neutral"
            else:
                regime = "bear"

        if regime == "bull" and not broken_hl and not np.isnan(last_hl) and close[i] < last_hl:
            choch_down = True
            choch_level = last_hl
            broken_hl = True
            regime = "neutral"

        if regime == "bear" and not broken_lh and not np.isnan(last_lh) and close[i] > last_lh:
            choch_up = True
            choch_level = last_lh
            broken_lh = True
            regime = "neutral"

        sweep_high = (
            not np.isnan(last_swing_high)
            and high[i] > last_swing_high
            and close[i] < last_swing_high
        )
        sweep_low = (
            not np.isnan(last_swing_low)
            and low[i] < last_swing_low
            and close[i] > last_swing_low
        )

        long_sl = last_hl if not np.isnan(last_hl) else last_swing_low
        short_sl = last_lh if not np.isnan(last_lh) else last_swing_high
        long_target = last_swing_high
        short_target = last_swing_low

        rows.append(
            {
                "ts": ts[i],
                "known_after_ts": known_after[i],
                "left_bars": cfg.left,
                "right_bars": cfg.right,
                "swing_type": swing_type,
                "swing_price": swing_price,
                "swing_ts": swing_ts,
                "confirm_ts": known_after[i] if swing_type else pd.NaT,
                "confirm_bars": cfg.right if swing_type else 0,
                "structure_label": structure_label,
                "regime": regime,
                "last_swing_high": last_swing_high,
                "last_swing_high_ts": last_swing_high_ts,
                "last_swing_low": last_swing_low,
                "last_swing_low_ts": last_swing_low_ts,
                "last_hh": last_hh,
                "last_hh_ts": last_hh_ts,
                "last_hl": last_hl,
                "last_hl_ts": last_hl_ts,
                "last_lh": last_lh,
                "last_lh_ts": last_lh_ts,
                "last_ll": last_ll,
                "last_ll_ts": last_ll_ts,
                "bos_up": bos_up,
                "bos_down": bos_down,
                "choch_up": choch_up,
                "choch_down": choch_down,
                "sweep_high": sweep_high,
                "sweep_low": sweep_low,
                "bos_level": bos_level,
                "choch_level": choch_level,
                "long_structural_sl": long_sl,
                "short_structural_sl": short_sl,
                "long_target_1": long_target,
                "short_target_1": short_target,
                "dist_to_long_sl_pct": _dist_pct(close[i], long_sl, long=True),
                "dist_to_short_sl_pct": _dist_pct(close[i], short_sl, long=False),
                "dist_to_long_target_pct": _target_pct(close[i], long_target, long=True),
                "dist_to_short_target_pct": _target_pct(close[i], short_target, long=False),
            }
        )

    out = pd.DataFrame(rows)
    bool_cols = ["bos_up", "bos_down", "choch_up", "choch_down", "sweep_high", "sweep_low"]
    for col in bool_cols:
        out[col] = out[col].astype(bool)
    return out


def _confirmed_pivots(high: np.ndarray, low: np.ndarray, ts: list, cfg: StructureConfig) -> list[dict]:
    events = []
    last_type = ""
    last_event_idx = -1
    for pivot_i in range(cfg.left, len(high) - cfg.right):
        left = pivot_i - cfg.left
        right = pivot_i + cfg.right + 1
        is_high = high[pivot_i] > high[left:pivot_i].max() and high[pivot_i] > high[pivot_i + 1:right].max()
        is_low = low[pivot_i] < low[left:pivot_i].min() and low[pivot_i] < low[pivot_i + 1:right].min()
        if not is_high and not is_low:
            continue

        event = {
            "confirm_i": pivot_i + cfg.right,
            "pivot_i": pivot_i,
            "pivot_ts": ts[pivot_i],
            "swing_type": "high" if is_high else "low",
            "price": float(high[pivot_i] if is_high else low[pivot_i]),
        }

        if last_type == event["swing_type"] and last_event_idx >= 0:
            # Causal rule: do not retroactively replace a confirmed pivot with
            # a later, more extreme same-type pivot. Full-history replacement
            # makes online/live structure differ from backtest structure.
            continue

        events.append(event)
        last_type = event["swing_type"]
        last_event_idx = len(events) - 1
    return events


def _infer_bar_delta(ts: pd.Series) -> pd.Timedelta:
    diffs = ts.sort_values().diff().dropna()
    if diffs.empty:
        return pd.Timedelta(0)
    return diffs.median()


def _dist_pct(price: float, level: float, *, long: bool) -> float:
    if np.isnan(level) or price <= 0:
        return np.nan
    dist = (price - level) / price if long else (level - price) / price
    return float(dist) if dist > 0 else np.nan


def _target_pct(price: float, level: float, *, long: bool) -> float:
    if np.isnan(level) or price <= 0:
        return np.nan
    dist = (level - price) / price if long else (price - level) / price
    return float(dist) if dist > 0 else np.nan


def _validate(df: pd.DataFrame, cfg: StructureConfig) -> None:
    missing = {"ts", "open", "high", "low", "close"} - set(df.columns)
    if missing:
        raise ValueError(f"Missing OHLC columns: {sorted(missing)}")
    if cfg.left < 1 or cfg.right < 1:
        raise ValueError("left and right must be >= 1")
