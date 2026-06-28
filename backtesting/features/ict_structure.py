"""Strict causal ICT market-structure state machine.

This module is intentionally simpler than the broad structure feature index:

    bullish: HH/HL structure confirmed by bullish BOS
    bearish CHoCH: close below protected HL
    bearish setup: LL + LH form after CHoCH
    bearish: close below the new LL confirms bearish BOS

The long side is the mirror image. CHoCH is transitional, not a direction by
itself. A strategy should treat `direction_bias == 0` as no-trade/range.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IctStructureConfig:
    left: int = 3
    right: int = 3


def build_ict_structure_index(df: pd.DataFrame, config: IctStructureConfig | None = None) -> pd.DataFrame:
    cfg = config or IctStructureConfig()
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

    events_by_confirm: dict[int, list[dict]] = {}
    for event in _confirmed_pivots(high, low, ts, cfg):
        events_by_confirm.setdefault(event["confirm_i"], []).append(event)

    last_swing_high = np.nan
    last_swing_low = np.nan
    last_hh = np.nan
    last_hl = np.nan
    last_lh = np.nan
    last_ll = np.nan
    protected_high = np.nan
    protected_low = np.nan
    state = "neutral"
    pending_down_ll = False
    pending_down_lh = False
    pending_up_hh = False
    pending_up_hl = False
    broken_levels: set[tuple[str, float]] = set()
    swing_path: list[tuple[int, float]] = []
    rows = []

    for i in range(n):
        swing_type = ""
        swing_price = np.nan
        swing_ts = pd.NaT
        structure_label = ""

        for event in events_by_confirm.get(i, []):
            swing_type = event["swing_type"]
            swing_price = float(event["price"])
            swing_ts = event["pivot_ts"]
            swing_path.append((i, swing_price))

            if swing_type == "high":
                if np.isnan(last_swing_high):
                    structure_label = "1H"
                elif swing_price > last_swing_high:
                    structure_label = "HH"
                    last_hh = swing_price
                    if state == "transition_up":
                        pending_up_hh = True
                else:
                    structure_label = "LH"
                    last_lh = swing_price
                    if state == "bearish":
                        protected_high = swing_price
                    if state == "transition_down":
                        pending_down_lh = True
                last_swing_high = swing_price

            else:
                if np.isnan(last_swing_low):
                    structure_label = "1L"
                elif swing_price > last_swing_low:
                    structure_label = "HL"
                    last_hl = swing_price
                    if state == "bullish":
                        protected_low = swing_price
                    if state == "transition_up":
                        pending_up_hl = True
                else:
                    structure_label = "LL"
                    last_ll = swing_price
                    if state == "transition_down":
                        pending_down_ll = True
                last_swing_low = swing_price

        bullish_choch = False
        bearish_choch = False
        bullish_bos = False
        bearish_bos = False
        choch_level = np.nan
        bos_level = np.nan

        if state == "bullish" and not np.isnan(protected_low) and close[i] < protected_low:
            key = ("bearish_choch", float(protected_low))
            if key not in broken_levels:
                bearish_choch = True
                choch_level = protected_low
                broken_levels.add(key)
            state = "transition_down"
            pending_down_ll = False
            pending_down_lh = False

        elif state == "bearish" and not np.isnan(protected_high) and close[i] > protected_high:
            key = ("bullish_choch", float(protected_high))
            if key not in broken_levels:
                bullish_choch = True
                choch_level = protected_high
                broken_levels.add(key)
            state = "transition_up"
            pending_up_hh = False
            pending_up_hl = False

        if state in ("neutral", "transition_up"):
            if pending_up_hh and pending_up_hl and not np.isnan(last_hh) and close[i] > last_hh:
                key = ("bullish_bos", float(last_hh))
                if key not in broken_levels:
                    bullish_bos = True
                    bos_level = last_hh
                    broken_levels.add(key)
                state = "bullish"
                protected_low = last_hl
                protected_high = np.nan
                pending_up_hh = False
                pending_up_hl = False

        if state in ("neutral", "transition_down"):
            if pending_down_ll and pending_down_lh and not np.isnan(last_ll) and close[i] < last_ll:
                key = ("bearish_bos", float(last_ll))
                if key not in broken_levels:
                    bearish_bos = True
                    bos_level = last_ll
                    broken_levels.add(key)
                state = "bearish"
                protected_high = last_lh
                protected_low = np.nan
                pending_down_ll = False
                pending_down_lh = False

        if state == "neutral":
            if not np.isnan(last_hh) and not np.isnan(last_hl) and close[i] > last_hh:
                bullish_bos = True
                bos_level = last_hh
                state = "bullish"
                protected_low = last_hl
            elif not np.isnan(last_ll) and not np.isnan(last_lh) and close[i] < last_ll:
                bearish_bos = True
                bos_level = last_ll
                state = "bearish"
                protected_high = last_lh

        direction_bias = 1 if state == "bullish" else -1 if state == "bearish" else 0
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
                "structure_label": structure_label,
                "ict_state": state,
                "direction_bias": direction_bias,
                "bullish_choch": bullish_choch,
                "bearish_choch": bearish_choch,
                "bullish_bos": bullish_bos,
                "bearish_bos": bearish_bos,
                "choch_level": choch_level,
                "bos_level": bos_level,
                "last_hh": last_hh,
                "last_hl": last_hl,
                "last_lh": last_lh,
                "last_ll": last_ll,
                "protected_high": protected_high,
                "protected_low": protected_low,
                "zigzag_level": _zigzag_level(i, swing_path),
            }
        )

    out = pd.DataFrame(rows)
    for col in ["bullish_choch", "bearish_choch", "bullish_bos", "bearish_bos"]:
        out[col] = out[col].astype(bool)
    return out


def _confirmed_pivots(high: np.ndarray, low: np.ndarray, ts: list, cfg: IctStructureConfig) -> list[dict]:
    raw = []
    for pivot_i in range(cfg.left, len(high) - cfg.right):
        left = pivot_i - cfg.left
        right = pivot_i + cfg.right + 1
        is_high = high[pivot_i] > high[left:pivot_i].max() and high[pivot_i] > high[pivot_i + 1 : right].max()
        is_low = low[pivot_i] < low[left:pivot_i].min() and low[pivot_i] < low[pivot_i + 1 : right].min()
        if is_high:
            raw.append((pivot_i, "high", float(high[pivot_i])))
        elif is_low:
            raw.append((pivot_i, "low", float(low[pivot_i])))

    events: list[dict] = []
    for pivot_i, swing_type, price in raw:
        if events and events[-1]["swing_type"] == swing_type:
            prev = events[-1]
            replace = (swing_type == "high" and price > prev["price"]) or (swing_type == "low" and price < prev["price"])
            if replace:
                events[-1] = _event(pivot_i, swing_type, price, ts, cfg)
            continue
        events.append(_event(pivot_i, swing_type, price, ts, cfg))
    return events


def _event(pivot_i: int, swing_type: str, price: float, ts: list, cfg: IctStructureConfig) -> dict:
    return {
        "confirm_i": pivot_i + cfg.right,
        "pivot_i": pivot_i,
        "pivot_ts": ts[pivot_i],
        "swing_type": swing_type,
        "price": price,
    }


def _zigzag_level(i: int, swing_path: list[tuple[int, float]]) -> float:
    if not swing_path:
        return np.nan
    if len(swing_path) == 1:
        return float(swing_path[-1][1])
    i0, p0 = swing_path[-2]
    i1, p1 = swing_path[-1]
    if i1 == i0:
        return float(p1)
    if i <= i0:
        return float(p0)
    frac = min(1.0, max(0.0, (i - i0) / (i1 - i0)))
    return float(p0 + frac * (p1 - p0))


def _infer_bar_delta(ts: pd.Series) -> pd.Timedelta:
    diffs = ts.sort_values().diff().dropna()
    if diffs.empty:
        return pd.Timedelta(0)
    return diffs.median()


def _validate(df: pd.DataFrame, cfg: IctStructureConfig) -> None:
    missing = {"ts", "open", "high", "low", "close"} - set(df.columns)
    if missing:
        raise ValueError(f"Missing OHLC columns: {sorted(missing)}")
    if cfg.left < 1 or cfg.right < 1:
        raise ValueError("left and right must be >= 1")
