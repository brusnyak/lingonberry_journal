#!/usr/bin/env python3
"""
Forex V1 — Multi-TF Structure-Based Strategy

Clean build. No inheritance from V2/V3. No VWAP, no EMA, no ATR stops.

Pipeline:
  4H → structure (HH/HL/LH/LL) → macro bias
  1H → structure → confluence bias (optional)
  15m → structure + sweep detection + MSS (Market Structure Shift)
  1m/5m → FVG retest → entry → trailing on 1m structure

Entry sequence (all must pass):
  1. Higher TF structure → bias direction
  2. 15m sweep of a swing point (wick + body reclaim)
  3. 15m MSS (displacement BOS in bias direction)
  4. Lower TF FVG retest (price inside MSS displacement FVG)

Stop: structural — below swept low (longs) / above swept high (shorts)
Exit: hybrid — partial scale-out at key levels + structure trail

Run:
  python backtesting/forex_v1.py
  python backtesting/forex_v1.py --pairs GBPUSD,EURUSD --entry-tf 1 --days 30
  python backtesting/forex_v1.py --sweep  (full config sweep)
  python backtesting/forex_v1.py --monthly (rolling monthly windows)
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

_SCRIPT = Path(__file__).parent
_ROOT   = _SCRIPT.parent
sys.path.insert(0, str(_ROOT))

from backtesting.structure_lib.swing  import swing_points
from backtesting.structure_lib.labels import label_structure
from backtesting.structure_lib.fvg    import detect_fvgs, FVG


# ═════════════════════════════════════════════════════════════════════════════
# Constants
# ═════════════════════════════════════════════════════════════════════════════

DATA_DIR = _ROOT / "data" / "market_data"
CASH     = 10_000.0
COMM     = 0.75       # USD per side
RNG      = np.random.default_rng(42)

# Swing lengths per timeframe
SWING_LEN = {"240": 3, "60": 5, "15": 5, "5": 8, "1": 10}

# Default TF hierarchy
BIAS_TFS   = ["240", "60"]   # 4H, 1H
TRIGGER_TF = "15"            # sweep + MSS detection
ENTRY_TF   = "1"             # execution (or "5")


# ═════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Sweep:
    """A liquidity sweep event on the trigger TF."""
    direction: str      # "bullish" (swept low) or "bearish" (swept high)
    level: float        # the price level that was swept
    sweep_bar: int      # index of the bar that swept the level
    reclaim_bar: int    # index of the bar that reclaimed (body close inside)
    swing_idx: int      # index of the swing point that was swept


@dataclass
class MSS:
    """A Market Structure Shift — sweep + displacement BOS."""
    direction: str      # "bullish" or "bearish"
    sweep: Sweep
    bos_bar: int        # index of the displacement BOS bar
    fvg: Optional[FVG] = None  # FVG formed during displacement


@dataclass
class Trade:
    direction:     str
    entry_ts:      pd.Timestamp
    entry_price:   float
    stop:          float
    lots:          float
    # Targets for partial exits
    tp1:           float = 0.0  # 50% close level
    tp2:           float = 0.0  # 30% close level
    # State
    partial1_closed: bool = False
    partial2_closed: bool = False
    stop_moved_to_be: bool = False
    trail_high:    float = 0.0
    trail_low:     float = 999.0
    # Metadata
    bias_4h:       str = ""
    bias_1h:       str = ""
    sweep_level:   float = 0.0
    mss_bar:       int = 0
    # Exit
    exit_ts:       Optional[pd.Timestamp] = None
    exit_price:    Optional[float] = None
    exit_reason:   str = ""
    pnl:           float = 0.0


@dataclass
class Config:
    # Data
    entry_tf:    str = "1"   # "1" or "5"
    days:        int = 30
    # Bias
    bias_mode:   str = "4h1h"   # "4h", "1h", "4h1h" (both required)
    # Entry
    require_sweep: bool = True
    # Exit
    partials:   str = "50/30/20"  # "50/50", "30/30/40", "100"
    target_mode: str = "all"      # "daily", "session", "fvg50", "fib", "all"
    # Risk
    risk_pct:   float = 0.005  # 0.5% per trade


# ═════════════════════════════════════════════════════════════════════════════
# Data Loading
# ═════════════════════════════════════════════════════════════════════════════

def load_tf(symbol: str, tf: str, days: int = 30) -> pd.DataFrame:
    """Load a single timeframe parquet file."""
    f = DATA_DIR / f"{symbol}{tf}.parquet"
    if not f.exists():
        raise FileNotFoundError(f"Missing data: {f}")
    df = pd.read_parquet(f)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.sort_values("ts").reset_index(drop=True)
    if days and len(df) > 0:
        cutoff = df["ts"].max() - pd.Timedelta(days=days)
        df = df[df["ts"] >= cutoff].reset_index(drop=True)
    return df


def load_multi_tf(symbol: str, tfs: list[str], days: int = 30) -> dict[str, pd.DataFrame]:
    """Load multiple timeframes. Returns {tf: df}."""
    return {tf: load_tf(symbol, tf, days=days) for tf in tfs}


# ═════════════════════════════════════════════════════════════════════════════
# Structure Labels (per TF)
# ═════════════════════════════════════════════════════════════════════════════

def compute_structure(df: pd.DataFrame, swing_length: int) -> pd.DataFrame:
    """Compute HH/HL/LH/LL, trend, BOS/CHoCH for a single TF.

    Returns a DataFrame indexed like df with structure columns.
    """
    swings, levels = swing_points(df, swing_length=swing_length)
    struct = label_structure(df, swings, levels)
    struct["swing"] = swings.values
    struct["swing_level"] = levels.values
    return struct


# ═════════════════════════════════════════════════════════════════════════════
# Sweep Detection (Trigger TF)
# ═════════════════════════════════════════════════════════════════════════════

def detect_sweeps(
    df: pd.DataFrame,
    swings: np.ndarray,
    levels: np.ndarray,
    lookback: int = 20,
) -> list[Sweep]:
    """Detect ICT liquidity sweeps.

    A sweep occurs when a wick extends beyond a swing point AND the body
    closes back inside the level (reclamation), all on the SAME bar.

    Rules (from ICT research):
      - Wick beyond level + body reclaim inside = sweep
      - No reclamation = failed breakout, not a sweep
      - close[1] basis: use confirmed previous bar
    """
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(df)

    sweeps: list[Sweep] = []

    for i in range(lookback, n):
        c = close[i]
        h = high[i]
        l = low[i]

        # Check against recent swing points
        for j in range(max(0, i - lookback), i):
            sv = swings[j]
            if np.isnan(sv):
                continue
            level = levels[j]

            if sv == 1:  # Swing high → potential bearish sweep (sweep above)
                # Wick above + body reclaims
                if h > level and c < level:
                    sweeps.append(Sweep(
                        direction="bearish",
                        level=level,
                        sweep_bar=i,
                        reclaim_bar=i,
                        swing_idx=j,
                    ))
                    break  # one sweep per bar

            elif sv == -1:  # Swing low → potential bullish sweep (sweep below)
                if l < level and c > level:
                    sweeps.append(Sweep(
                        direction="bullish",
                        level=level,
                        sweep_bar=i,
                        reclaim_bar=i,
                        swing_idx=j,
                    ))
                    break  # one sweep per bar

    return sweeps


# ═════════════════════════════════════════════════════════════════════════════
# MSS Detection (Trigger TF)
# ═════════════════════════════════════════════════════════════════════════════

def detect_mss(
    df: pd.DataFrame,
    sweeps: list[Sweep],
    struct: pd.DataFrame,
    fvgs: list[FVG],
    lookback: int = 12,
) -> list[MSS]:
    """Detect Market Structure Shifts.

    An MSS = sweep + subsequent displacement BOS in the OPPOSITE direction
    of the sweep (which IS the bias direction).

    For a bullish MSS:
      - Sweep of a low (bullish sweep)
      - Within lookback bars: bullish BOS (close above last HH)

    For a bearish MSS:
      - Sweep of a high (bearish sweep)
      - Within lookback bars: bearish BOS (close below last LL)

    Returns list of MSS events.
    """
    bull_bos = struct["bullish_bos"].values
    bear_bos = struct["bearish_bos"].values
    n = len(df)

    # Build FVG lookup: for each bar, what FVGs start here?
    fvg_by_start = {}
    for fvg in fvgs:
        if fvg.c3_idx not in fvg_by_start:
            fvg_by_start[fvg.c3_idx] = []
        fvg_by_start[fvg.c3_idx].append(fvg)

    mss_list: list[MSS] = []
    seen_mss = set()  # dedup by (bos_bar, direction)

    for sweep in sweeps:
        start = sweep.reclaim_bar + 1
        end = min(start + lookback, n)

        for bos_i in range(start, end):
            # Bullish sweep → look for bullish BOS
            if sweep.direction == "bullish" and bull_bos[bos_i]:
                # Check if an FVG formed during/after this BOS
                fvg = None
                # Look for FVGs that formed near this bar
                for bi in range(max(0, bos_i - 1), min(bos_i + 5, n)):
                    if bi in fvg_by_start:
                        for f in fvg_by_start[bi]:
                            if f.kind == "bullish":
                                fvg = f
                                break
                    if fvg:
                        break
                key = (bos_i, "bullish")
                if key not in seen_mss:
                    seen_mss.add(key)
                    mss_list.append(MSS(
                        direction="bullish",
                        sweep=sweep,
                        bos_bar=bos_i,
                        fvg=fvg,
                    ))
                break  # one MSS per sweep

            # Bearish sweep → look for bearish BOS
            elif sweep.direction == "bearish" and bear_bos[bos_i]:
                fvg = None
                for bi in range(max(0, bos_i - 1), min(bos_i + 5, n)):
                    if bi in fvg_by_start:
                        for f in fvg_by_start[bi]:
                            if f.kind == "bearish":
                                fvg = f
                                break
                    if fvg:
                        break
                key = (bos_i, "bearish")
                if key not in seen_mss:
                    seen_mss.add(key)
                    mss_list.append(MSS(
                        direction="bearish",
                        sweep=sweep,
                        bos_bar=bos_i,
                        fvg=fvg,
                    ))
                break

    return mss_list


# ═════════════════════════════════════════════════════════════════════════════
# Multi-TF Alignment
# ═════════════════════════════════════════════════════════════════════════════

def align_bias_to_entry(
    df_entry: pd.DataFrame,
    df_bias: pd.DataFrame,
    bias_tf_minutes: int,
) -> np.ndarray:
    """Map higher TF trend labels to entry TF bars via forward fill.

    Returns array of trend values ('bullish', 'bearish', 'neutral').
    """
    ts_entry = pd.to_datetime(df_entry["ts"])
    ts_bias = pd.to_datetime(df_bias["ts"])

    # Floor entry timestamps to bias TF intervals
    entry_rounded = ts_entry.dt.floor(f"{bias_tf_minutes}min")

    # Build bias lookup: {rounded_ts: trend}
    bias_map = dict(zip(
        pd.to_datetime(df_bias["ts"]).dt.floor(f"{bias_tf_minutes}min"),
        df_bias["trend"].values,
    ))

    # Map and forward fill
    bias_aligned = np.array([bias_map.get(ts, "neutral") for ts in entry_rounded])
    # Forward fill: once bias changes, propagate
    last = "neutral"
    for i in range(len(bias_aligned)):
        if bias_aligned[i] != "neutral":
            last = bias_aligned[i]
        else:
            bias_aligned[i] = last

    return bias_aligned


def map_mss_to_entry(
    df_entry: pd.DataFrame,
    df_trigger: pd.DataFrame,
    mss_list: list[MSS],
    trigger_tf_minutes: int,
    max_active_bars: int = 48,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Map MSS events from trigger TF to entry TF bars.

    Returns arrays aligned to entry TF:
      mss_active: bool array — True if an MSS is currently active
      mss_direction: str array — direction of active MSS
      mss_fvg_top: float array — top of entry FVG zone
      mss_fvg_bottom: float array — bottom of entry FVG zone
    """
    ts_entry = pd.to_datetime(df_entry["ts"])
    ts_trigger = pd.to_datetime(df_trigger["ts"])

    n = len(ts_entry)

    mss_active = np.zeros(n, dtype=bool)
    mss_dir = np.full(n, "", dtype=object)
    mss_top = np.full(n, np.nan)
    mss_bottom = np.full(n, np.nan)

    trigger_n = len(ts_trigger)
    for mss in mss_list:
        if mss.fvg is None:
            continue

        # Skip MSS too close to data end (no room for entries)
        if mss.bos_bar > trigger_n - 20:
            continue

        # MSS becomes active at the BOS bar close
        bos_ts = ts_trigger.iloc[mss.bos_bar] if mss.bos_bar < trigger_n else None
        if bos_ts is None:
            continue

        # Find the entry bar closest to the BOS bar
        entry_start = np.searchsorted(ts_entry, bos_ts)

        # MSS stays active for max_active_bars or until FVG is filled
        expiry_idx = min(mss.bos_bar + max_active_bars, len(ts_trigger) - 1)
        expiry = ts_trigger.iloc[expiry_idx]

        entry_end = min(np.searchsorted(ts_entry, expiry), n)

        fvg_top = mss.fvg.top if mss.direction == "bullish" else mss.fvg.bottom
        fvg_bottom = mss.fvg.bottom if mss.direction == "bullish" else mss.fvg.top

        for i in range(entry_start, entry_end):
            if not mss_active[i]:  # first MSS wins
                mss_active[i] = True
                mss_dir[i] = mss.direction
                mss_top[i] = fvg_top
                mss_bottom[i] = fvg_bottom

    return mss_active, mss_dir, mss_top, mss_bottom


# ═════════════════════════════════════════════════════════════════════════════
# Cost Model
# ═════════════════════════════════════════════════════════════════════════════

def random_spread(pip: float) -> float:
    """Random entry spread: 1-3 pips."""
    return pip * RNG.uniform(1.0, 3.0)


def random_exit_spread(pip: float) -> float:
    """Random exit spread: 0.5-1.5 pips (limit fills at half spread)."""
    return pip * RNG.uniform(0.5, 1.5)


def random_slippage(pip: float) -> float:
    """Random slippage on stop hits: 0-1 pip."""
    return pip * RNG.uniform(0.0, 1.0)


# ═════════════════════════════════════════════════════════════════════════════
# Exit Logic
# ═════════════════════════════════════════════════════════════════════════════

def compute_targets(
    entry_price: float, direction: str, stop: float,
    df_1d: pd.DataFrame, df_1h: pd.DataFrame,
    struct_15m: pd.DataFrame, mss: MSS, config: Config,
) -> tuple[float, float]:
    """Compute TP1 (50%) and TP2 (30%) levels.

    Gathers all candidate levels, sorts by proximity, assigns TP1 and TP2.
    """
    candidates: list[float] = []

    if config.target_mode in ("daily", "all"):
        # Previous day high/low
        last_day = df_1d.iloc[-1] if len(df_1d) > 0 else None
        if last_day is not None:
            if direction == "long":
                candidates.append(last_day["high"])
            else:
                candidates.append(last_day["low"])

    if config.target_mode in ("session", "all"):
        # Current 1H session high/low
        last_hour = df_1h.iloc[-1] if len(df_1h) > 0 else None
        if last_hour is not None:
            if direction == "long":
                candidates.append(last_hour["high"])
            else:
                candidates.append(last_hour["low"])

    if config.target_mode in ("fvg50", "all"):
        # 50% FVG (CE) of the MSS displacement FVG
        if mss.fvg is not None:
            candidates.append(mss.fvg.ce)

    if config.target_mode in ("fib", "all"):
        # Fib extension of the sweep → BOS range
        sweep_level = mss.sweep.level
        bos_bar = mss.bos_bar
        # Use the high/low around the displacement
        if direction == "long":
            fib_range = entry_price - sweep_level
            if fib_range > 0:
                candidates.append(entry_price + fib_range * 1.0)      # 1.0
                candidates.append(entry_price + fib_range * 1.272)    # 1.272
                candidates.append(entry_price + fib_range * 1.618)    # 1.618
        else:
            fib_range = sweep_level - entry_price
            if fib_range > 0:
                candidates.append(entry_price - fib_range * 1.0)
                candidates.append(entry_price - fib_range * 1.272)
                candidates.append(entry_price - fib_range * 1.618)

    if not candidates:
        # Fallback: use stop distance × 1.5 and × 3
        stop_dist = abs(entry_price - stop)
        candidates = [
            entry_price + stop_dist * 1.5 if direction == "long" else entry_price - stop_dist * 1.5,
            entry_price + stop_dist * 3.0 if direction == "long" else entry_price - stop_dist * 3.0,
        ]

    # Filter: only levels beyond entry in the right direction
    valid = []
    for level in candidates:
        if direction == "long" and level > entry_price:
            valid.append(level)
        elif direction == "short" and level < entry_price:
            valid.append(level)

    if not valid:
        return candidates[0] if candidates else (entry_price + 0.001), \
               candidates[-1] if len(candidates) > 1 else (entry_price + 0.002)

    valid = sorted(set(valid))
    if direction == "short":
        valid = sorted(valid, reverse=True)

    # TP1 = nearest valid target, TP2 = furthest valid target (or next nearest)
    tp1 = valid[0]
    tp2 = valid[-1] if len(valid) > 1 else valid[0]

    return tp1, tp2


# ═════════════════════════════════════════════════════════════════════════════
# Position Sizing
# ═════════════════════════════════════════════════════════════════════════════

def calc_position(equity: float, stop_dist: float, risk_pct: float, mult: int) -> float:
    """Calculate lot size based on risk percentage."""
    if stop_dist <= 0:
        return 0.01
    raw = (equity * risk_pct) / (stop_dist * mult)
    return max(min(round(math.floor(raw / 0.01) * 0.01, 2), 20.0), 0.01)


# ═════════════════════════════════════════════════════════════════════════════
# Backtest Engine
# ═════════════════════════════════════════════════════════════════════════════

def backtest(
    data: dict[str, pd.DataFrame],  # all TF dataframes
    trigger_struct: pd.DataFrame,    # 15m structure
    trigger_sweeps: list[Sweep],     # 15m sweeps
    trigger_mss: list[MSS],          # 15m MSS events
    bias_arrays: dict[str, np.ndarray],  # bias arrays for entry TF
    mss_entry: tuple,                # mapped MSS arrays on entry TF
    df_1d: pd.DataFrame,             # daily data for targets
    df_1h: pd.DataFrame,             # 1H data for targets
    config: Config,
) -> list[Trade]:
    """Run the backtest on entry TF bars.

    Uses pre-computed structure, sweeps, MSS mapped to entry TF.
    """
    df_entry = data[config.entry_tf]
    ts_arr = pd.to_datetime(df_entry["ts"]).values
    open_arr = df_entry["open"].values
    high_arr = df_entry["high"].values
    low_arr = df_entry["low"].values
    close_arr = df_entry["close"].values

    mss_active, mss_dir, mss_top, mss_bottom = mss_entry

    # Add ATR to entry DF
    df_entry = _add_atr(df_entry)

    pip = 0.0001
    mult = 100_000
    equity = CASH
    pos: Optional[Trade] = None
    trades: list[Trade] = []

    n = len(df_entry)

    # Pre-create default bias arrays (avoid np.full per iteration)
    _neutral_bias = np.full(n, "neutral", dtype=object)

    # Pre-parse partials config
    partial_pcts = [float(p) / 100.0 for p in config.partials.split("/")]
    # Pad to 3 entries (50/30/20 style)
    while len(partial_pcts) < 3:
        partial_pcts.append(0.0)

    for i in range(n):
        ts = pd.Timestamp(ts_arr[i])
        o = open_arr[i]
        h = high_arr[i]
        l = low_arr[i]
        c = close_arr[i]

        # ── Check active position ──
        if pos is not None:
            # Update trailing levels
            if pos.direction == "long":
                pos.trail_high = max(pos.trail_high, h)
                if l < pos.trail_low:
                    pos.trail_low = l
            else:
                pos.trail_low = min(pos.trail_low, l)
                if h > pos.trail_high:
                    pos.trail_high = h

            # Check partial 1 (50%) — nearest target
            if not pos.partial1_closed:
                hit = (pos.direction == "long" and h >= pos.tp1) or \
                      (pos.direction == "short" and l <= pos.tp1)
                if hit:
                    # Close 50%
                    exit_price = pos.tp1
                    spread_cost = random_exit_spread(pip)
                    fill = exit_price - spread_cost if pos.direction == "long" else exit_price + spread_cost
                    sign = 1 if pos.direction == "long" else -1
                    partial_pnl = sign * (fill - pos.entry_price) * pos.lots * mult * partial_pcts[0] - COMM * partial_pcts[0]
                    equity += partial_pnl
                    pos.partial1_closed = True
                    if partial_pcts[0] > 0:
                        # Move stop to BE on remaining
                        pos.stop = pos.entry_price
                        pos.stop_moved_to_be = True

            # Check partial 2 (30%)
            if pos.partial1_closed and not pos.partial2_closed:
                hit = (pos.direction == "long" and h >= pos.tp2) or \
                      (pos.direction == "short" and l <= pos.tp2)
                if hit:
                    exit_price = pos.tp2
                    spread_cost = random_exit_spread(pip)
                    fill = exit_price - spread_cost if pos.direction == "long" else exit_price + spread_cost
                    sign = 1 if pos.direction == "long" else -1
                    partial_pnl = sign * (fill - pos.entry_price) * pos.lots * mult * partial_pcts[1] - COMM * partial_pcts[1]
                    equity += partial_pnl
                    pos.partial2_closed = True

            # Check 1m structure trailing for the runner (20%)
            if pos.partial2_closed or (pos.partial1_closed and partial_pcts[2] > 0 and pos.stop_moved_to_be):
                # Trail on 1m structure: for longs, use recent HL; for shorts, use recent LH
                # Simplified: trail at bar's low - 1 ATR for longs, high + 1 ATR for shorts
                # (full 1m structure trail would need per-bar structure labels)
                if pos.direction == "long":
                    # Use the lowest low since entry as trailing level with buffer
                    trail_level = pos.trail_low
                    if trail_level < pos.trail_high:  # only trail if we've moved
                        pass  # keep current stop
                else:
                    trail_level = pos.trail_high

            # Check stop hit
            stop_hit = (pos.direction == "long" and l <= pos.stop) or \
                       (pos.direction == "short" and h >= pos.stop)

            if stop_hit:
                exit_price = pos.stop
                spread_cost = random_exit_spread(pip) + random_slippage(pip)
                fill = exit_price - spread_cost if pos.direction == "long" else exit_price + spread_cost
                sign = 1 if pos.direction == "long" else -1
                remaining_pct = 1.0
                if pos.partial1_closed:
                    remaining_pct -= partial_pcts[0]
                if pos.partial2_closed:
                    remaining_pct -= partial_pcts[1]
                pos.pnl = sign * (fill - pos.entry_price) * pos.lots * mult * remaining_pct - COMM * remaining_pct
                pos.exit_ts = ts
                pos.exit_price = fill
                pos.exit_reason = "stop"
                equity += pos.pnl
                trades.append(pos)
                pos = None
                continue

            # Check if all partials done and runner stopped
            if pos.partial1_closed and pos.partial2_closed and partial_pcts[2] <= 0:
                pos.exit_ts = ts
                pos.exit_price = c  # fill at close
                pos.exit_reason = "complete"
                pos.pnl = 0.0
                trades.append(pos)
                pos = None
                continue

            continue  # position still open, skip entry

        # ── Entry Logic ──
        # 1. Check bias
        bias_4h = bias_arrays.get("240", _neutral_bias)[i]
        bias_1h = bias_arrays.get("60", _neutral_bias)[i]

        if config.bias_mode == "4h":
            if bias_4h == "neutral":
                continue
            want_long = bias_4h == "bullish"
            want_short = bias_4h == "bearish"
        elif config.bias_mode == "1h":
            if bias_1h == "neutral":
                continue
            want_long = bias_1h == "bullish"
            want_short = bias_1h == "bearish"
        else:  # "4h1h" — both required
            if bias_4h == "neutral" or bias_1h == "neutral":
                continue
            if bias_4h != bias_1h:
                continue  # must agree
            want_long = bias_4h == "bullish"
            want_short = bias_4h == "bearish"

        if not want_long and not want_short:
            continue

        # 2. Check active MSS in bias direction
        if not mss_active[i]:
            continue
        if mss_dir[i] == "":
            continue

        mss_is_bullish = mss_dir[i] == "bullish"
        if want_long and not mss_is_bullish:
            continue
        if want_short and mss_is_bullish:
            continue

        # 3. Check if price is inside the MSS FVG entry zone
        fvg_top = mss_top[i]
        fvg_bottom = mss_bottom[i]
        if np.isnan(fvg_top) or np.isnan(fvg_bottom):
            continue

        if want_long:
            # Price should be near or inside the FVG (below top, ideally near CE)
            if c > fvg_top:
                continue  # price already above the FVG zone
        else:
            if c < fvg_bottom:
                continue  # price already below the FVG zone

        # 4. Check if we're not too far past the FVG
        if want_long and c < fvg_bottom * 0.9995:  # 0.05% below — too far
            continue
        if want_short and c > fvg_top * 1.0005:  # 0.05% above — too far
            continue

        # ── Execute Entry ──
        direction = "long" if want_long else "short"
        entry_price = c

        # Stop: beyond the swept level with ATR(14) buffer
        sweep_level = None
        for mss in trigger_mss:
            if mss.direction == direction:
                sweep_level = mss.sweep.level
                break
        if sweep_level is None:
            continue

        # Calculate ATR(14) on entry TF for buffer
        atr = _compute_atr(df_entry, i)
        atr_buffer = atr * 0.5

        if direction == "long":
            stop = min(sweep_level - atr_buffer, entry_price - atr * 0.3)
        else:
            stop = max(sweep_level + atr_buffer, entry_price + atr * 0.3)

        stop_dist = abs(entry_price - stop)
        if stop_dist <= 0:
            continue

        lots = calc_position(equity, stop_dist, config.risk_pct, mult)

        # Apply spread
        spread_cost = random_spread(pip)
        entry_fill = entry_price + spread_cost if direction == "long" else entry_price - spread_cost

        # Compute targets
        df_day = df_1d
        df_hour = data.get("60", pd.DataFrame())
        struct_trig = trigger_struct
        mss_active_obj = next((m for m in trigger_mss if m.direction == direction), None)
        if mss_active_obj is None:
            continue

        tp1, tp2 = compute_targets(
            entry_fill, direction, stop,
            df_day, df_hour, struct_trig, mss_active_obj, config,
        )

        # Ensure TP levels make sense vs stop
        if direction == "long":
            if tp1 <= entry_fill + stop_dist * 0.3:
                tp1 = entry_fill + stop_dist * 1.5
            if tp2 <= tp1:
                tp2 = tp1 + stop_dist * 0.5
        else:
            if tp1 >= entry_fill - stop_dist * 0.3:
                tp1 = entry_fill - stop_dist * 1.5
            if tp2 >= tp1:
                tp2 = tp1 - stop_dist * 0.5

        pos = Trade(
            direction=direction,
            entry_ts=ts,
            entry_price=entry_fill,
            stop=stop,
            lots=lots,
            tp1=tp1,
            tp2=tp2,
            bias_4h=bias_4h,
            bias_1h=bias_1h,
            sweep_level=sweep_level if sweep_level else 0.0,
            trail_high=h if direction == "long" else h,
            trail_low=l if direction == "short" else l,
        )

    # Close any open position at end
    if pos is not None:
        remaining = 1.0
        if pos.partial1_closed:
            remaining -= partial_pcts[0]
        if pos.partial2_closed:
            remaining -= partial_pcts[1]
        pos.exit_ts = pd.Timestamp(ts_arr[-1])
        pos.exit_price = close_arr[-1]
        pos.exit_reason = "end"
        sign = 1 if pos.direction == "long" else -1
        pos.pnl = sign * (pos.exit_price - pos.entry_price) * pos.lots * mult * remaining - COMM * remaining
        trades.append(pos)

    return trades


def _add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add ATR(period) column to dataframe."""
    df = df.copy()
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(df)
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
    df["atr"] = pd.Series(tr).rolling(period, min_periods=1).mean().values
    return df


def _compute_atr(df: pd.DataFrame, i: int, period: int = 14) -> float:
    """Compute ATR at bar i."""
    if i < period + 1 and "atr" in df.columns and not pd.isna(df["atr"].iloc[i]):
        return df["atr"].iloc[i]
    if "atr" in df.columns and not pd.isna(df["atr"].iloc[i]):
        return df["atr"].iloc[i]
    # Fallback
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    tr_vals = []
    for j in range(max(0, i - period + 1), i + 1):
        tr = high[j] - low[j]
        if j > 0:
            tr = max(tr, abs(high[j] - close[j-1]), abs(low[j] - close[j-1]))
        tr_vals.append(tr)
    return float(np.mean(tr_vals)) if tr_vals else 0.001


# ═════════════════════════════════════════════════════════════════════════════
# Metrics
# ═════════════════════════════════════════════════════════════════════════════

def calc_metrics(trades: list[Trade]) -> dict:
    """Calculate performance metrics from trade list."""
    if not trades:
        return dict(n=0, wr=0.0, aw=0.0, al=0.0, rr=0.0, ret=0.0, dd=0.0,
                    sharpe=0.0, pf=0.0)

    pnls = np.array([t.pnl for t in trades])
    winners = pnls[pnls > 0]
    losers = pnls[pnls <= 0]
    n = len(pnls)
    wr = len(winners) / n if n > 0 else 0.0
    aw = float(winners.mean()) if len(winners) else 0.0
    al = float(abs(losers.mean())) if len(losers) else 1.0
    achieved_rr = aw / al if al else 0.0

    cum = np.cumsum(pnls) + CASH
    peak = np.maximum.accumulate(cum)
    dd = float(((peak - cum) / peak).max() * 100)
    ret = float(pnls.sum() / CASH * 100)
    std = float(pnls.std())
    sharpe = float(pnls.mean() / std * np.sqrt(252 * 1440)) if n > 1 and std > 0 else 0.0
    pf = float(winners.sum() / abs(losers.sum())) if len(losers) > 0 and losers.sum() < 0 else 0.0

    return dict(
        n=n, wr=wr, aw=aw, al=al, rr=achieved_rr,
        ret=ret, dd=dd, sharpe=sharpe, pf=pf,
    )


def trades_to_df(trades: list[Trade]) -> pd.DataFrame:
    """Export trades to DataFrame for CSV."""
    rows = []
    for t in trades:
        dur = int((t.exit_ts - t.entry_ts).total_seconds() / 60) if t.exit_ts else -1
        rows.append(dict(
            direction=t.direction,
            entry_ts=str(t.entry_ts)[:19],
            exit_ts=str(t.exit_ts)[:19] if t.exit_ts else "",
            duration_min=dur,
            entry_price=round(t.entry_price, 5),
            exit_price=round(t.exit_price, 5) if t.exit_price else None,
            stop=round(t.stop, 5),
            tp1=round(t.tp1, 5),
            tp2=round(t.tp2, 5),
            lots=t.lots,
            pnl=round(t.pnl, 2),
            exit_reason=t.exit_reason,
            bias_4h=t.bias_4h,
            bias_1h=t.bias_1h,
            sweep_level=round(t.sweep_level, 5),
            partial1=t.partial1_closed,
            partial2=t.partial2_closed,
        ))
    return pd.DataFrame(rows)


# ═════════════════════════════════════════════════════════════════════════════
# Config Sweeps
# ═════════════════════════════════════════════════════════════════════════════

BIAS_MODES = ["4h", "1h", "4h1h"]
PARTIALS_LIST = ["50/30/20", "50/50", "30/30/40", "100"]
TARGET_MODES = ["daily", "session", "fvg50", "fib", "all"]
SWEEP_MODES = [True, False]


def run_backtest_for_config(
    symbol: str, config: Config,
) -> list[Trade]:
    """Load data, compute structure, run backtest for one config.

    Returns list of trades.
    """
    # Load all TF data
    all_tfs = list(set([config.entry_tf, TRIGGER_TF] + BIAS_TFS + ["60", "1440"]))
    data = load_multi_tf(symbol, all_tfs, days=config.days)

    if config.entry_tf not in data or len(data[config.entry_tf]) == 0:
        return []

    # Compute structure on each bias TF
    bias_structs = {}
    for tf in BIAS_TFS:
        if tf in data and len(data[tf]) > 0:
            bias_structs[tf] = compute_structure(data[tf], SWING_LEN[tf])

    # Compute structure on trigger TF (15m)
    trigger_df = data[TRIGGER_TF]
    trigger_struct = compute_structure(trigger_df, SWING_LEN[TRIGGER_TF])

    # Sweep detection on trigger TF
    swings_t = trigger_struct["swing"].values
    levels_t = trigger_struct["swing_level"].values
    sweeps = detect_sweeps(trigger_df, swings_t, levels_t)

    # FVG detection on trigger TF
    fvgs_t = detect_fvgs(trigger_df)

    # MSS detection on trigger TF
    mss_list = detect_mss(trigger_df, sweeps, trigger_struct, fvgs_t)

    # Align bias to entry TF
    bias_arrays = {}
    for tf in BIAS_TFS:
        if tf in data and tf in bias_structs:
            bias_df = data[tf].copy()
            bias_df["trend"] = bias_structs[tf]["trend"].values
            bias_arr = align_bias_to_entry(
                data[config.entry_tf], bias_df, int(tf),
            )
            bias_arrays[tf] = bias_arr

    # Map MSS to entry TF
    mss_entry = map_mss_to_entry(
        data[config.entry_tf], trigger_df, mss_list, int(TRIGGER_TF),
    )

    # Daily data for targets
    df_1d = data.get("1440", pd.DataFrame())
    df_1h = data.get("60", pd.DataFrame())

    # Run backtest
    trades = backtest(
        data, trigger_struct, sweeps, mss_list,
        bias_arrays, mss_entry, df_1d, df_1h, config,
    )

    return trades


def run_sweep(pairs: list[str], base_config: Config) -> pd.DataFrame:
    """Run full config sweep across all combinations."""
    rows = []
    total = (len(pairs) * len(BIAS_MODES) * len(PARTIALS_LIST) *
             len(TARGET_MODES) * len(SWEEP_MODES))
    done = 0

    for pair in pairs:
        print(f"\n{pair}", flush=True)
        for bias_mode in BIAS_MODES:
            for partials in PARTIALS_LIST:
                for target_mode in TARGET_MODES:
                    for require_sweep in SWEEP_MODES:
                        cfg = Config(
                            entry_tf=base_config.entry_tf,
                            days=base_config.days,
                            bias_mode=bias_mode,
                            partials=partials,
                            target_mode=target_mode,
                            require_sweep=require_sweep,
                        )
                        t0 = time.time()
                        trades = run_backtest_for_config(pair, cfg)
                        m = calc_metrics(trades)
                        done += 1
                        rows.append(dict(
                            pair=pair, bias=bias_mode,
                            entry_tf=cfg.entry_tf,
                            partials=partials,
                            target=target_mode,
                            sweep_req=int(require_sweep),
                            **m,
                            trades=len(trades),
                            s=round(time.time() - t0, 1),
                        ))
                        print(
                            f"  [{done:>3}/{total}] {bias_mode:>5} "
                            f"{partials:>9} {target_mode:>8} "
                            f"sweep={'Y' if require_sweep else 'N'} | "
                            f"n={m['n']:>3} wr={m['wr']:.0%} "
                            f"rr={m['rr']:.2f} ret={m['ret']:>6.1f}% "
                            f"dd={m['dd']:.1f}% sharpe={m['sharpe']:.0f}",
                            flush=True,
                        )

    return pd.DataFrame(rows)


def run_monthly(pairs: list[str], base_config: Config) -> pd.DataFrame:
    """Run backtest on rolling monthly windows."""
    rows = []

    for pair in pairs:
        print(f"\n{pair} — monthly windows", flush=True)
        all_tfs = list(set([base_config.entry_tf, TRIGGER_TF] + BIAS_TFS + ["60", "1440"]))
        data = load_multi_tf(pair, all_tfs, days=0)  # full data

        entry_df = data[base_config.entry_tf]
        entry_df["ts"] = pd.to_datetime(entry_df["ts"])

        start_dates = pd.date_range(
            start=entry_df["ts"].min(),
            end=entry_df["ts"].max() - pd.Timedelta(days=30),
            freq="MS",
        )

        for start in start_dates:
            end = start + pd.Timedelta(days=30)
            # Slice all TFs to window
            window_data = {}
            for tf, df in data.items():
                df = df.copy()
                df["ts"] = pd.to_datetime(df["ts"])
                w = df[(df["ts"] >= start) & (df["ts"] < end)].reset_index(drop=True)
                if len(w) > 0:
                    window_data[tf] = w

            if len(window_data.get(base_config.entry_tf, pd.DataFrame())) < 500:
                continue

            # Run backtest on this window
            t0 = time.time()
            trigger_df = window_data.get(TRIGGER_TF, pd.DataFrame())
            if len(trigger_df) < 20:
                continue

            # Use default config for monthly runs
            cfg = Config(entry_tf=base_config.entry_tf, days=0, bias_mode="4h1h")

            # Compute structure
            bias_structs = {}
            for tf in BIAS_TFS:
                if tf in window_data and len(window_data[tf]) > 0:
                    bias_structs[tf] = compute_structure(window_data[tf], SWING_LEN[tf])

            trigger_struct = compute_structure(trigger_df, SWING_LEN[TRIGGER_TF])
            swings_t = trigger_struct["swing"].values
            levels_t = trigger_struct["swing_level"].values
            sweeps = detect_sweeps(trigger_df, swings_t, levels_t)
            fvgs_t = detect_fvgs(trigger_df)
            mss_list = detect_mss(trigger_df, sweeps, trigger_struct, fvgs_t)

            bias_arrays = {}
            for tf in BIAS_TFS:
                if tf in window_data and tf in bias_structs:
                    bias_df = window_data[tf].copy()
                    bias_df["trend"] = bias_structs[tf]["trend"].values
                    bias_arr = align_bias_to_entry(
                        window_data[cfg.entry_tf], bias_df, int(tf),
                    )
                    bias_arrays[tf] = bias_arr

            mss_entry = map_mss_to_entry(
                window_data[cfg.entry_tf], trigger_df, mss_list, int(TRIGGER_TF),
            )

            df_1d = window_data.get("1440", pd.DataFrame())
            df_1h = window_data.get("60", pd.DataFrame())

            trades = backtest(
                window_data, trigger_struct, sweeps, mss_list,
                bias_arrays, mss_entry, df_1d, df_1h, cfg,
            )
            m = calc_metrics(trades)

            window_label = f"{start.strftime('%b%d')}–{end.strftime('%b%d')}"
            rows.append(dict(
                pair=pair, window=window_label,
                start=str(start.date()), end=str(end.date()),
                bars=len(window_data.get(cfg.entry_tf, pd.DataFrame())),
                **m,
                trades=len(trades), s=round(time.time() - t0, 1),
            ))
            print(f"  {window_label}: n={m['n']:>3} wr={m['wr']:.0%} "
                  f"rr={m['rr']:.2f} ret={m['ret']:>6.1f}% dd={m['dd']:.1f}% "
                  f"sharpe={m['sharpe']:.0f}")

    return pd.DataFrame(rows)


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Forex V1 — Multi-TF Structure Strategy")
    parser.add_argument("--pairs", default="GBPUSD")
    parser.add_argument("--entry-tf", default="1", choices=["1", "5"])
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--sweep", action="store_true", help="Run full config sweep")
    parser.add_argument("--monthly", action="store_true", help="Run monthly rolling windows")
    parser.add_argument("--bias", default="4h1h", choices=["4h", "1h", "4h1h"],
                        help="Bias mode (default: 4h+1h both)")
    args = parser.parse_args()

    pairs = [p.strip().upper() for p in args.pairs.split(",")]

    if args.sweep:
        base = Config(entry_tf=args.entry_tf, days=args.days)
        results = run_sweep(pairs, base)
        out = _ROOT / "backtesting" / "results" / "forex_v1_sweep.csv"
    elif args.monthly:
        base = Config(entry_tf=args.entry_tf, days=0)
        results = run_monthly(pairs, base)
        out = _ROOT / "backtesting" / "results" / "forex_v1_monthly.csv"
    else:
        # Single run
        cfg = Config(entry_tf=args.entry_tf, days=args.days, bias_mode=args.bias)
        print(f"\nRunning {args.pairs} | entry={args.entry_tf} | bias={args.bias} | {args.days} days")
        all_trades = []
        for pair in pairs:
            trades = run_backtest_for_config(pair, cfg)
            m = calc_metrics(trades)
            all_trades.extend(trades)
            print(f"  {pair}: n={m['n']} wr={m['wr']:.0%} rr={m['rr']:.2f} "
                  f"ret={m['ret']:.1f}% dd={m['dd']:.1f}% sharpe={m['sharpe']:.0f}")

        results = pd.DataFrame([calc_metrics(all_trades)] if all_trades else [])
        out = _ROOT / "backtesting" / "results" / "forex_v1_single.csv"

    if len(results) > 0:
        out.parent.mkdir(exist_ok=True)
        results.to_csv(out, index=False)
        print(f"\nResults → {out}")

        # Pretty print
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 300)
        pd.set_option("display.float_format", "{:.2f}".format)

        if not results.empty:
            print(f"\n{'='*160}")
            print("ALL RESULTS")
            print(f"{'='*160}")
            print(results.to_string(index=False))


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    main()
