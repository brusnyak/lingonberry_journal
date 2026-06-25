#!/usr/bin/env python3
"""
Signal-level forward return diagnostic for TR Accumulation and TR Breakout.

Tests whether raw signal events have positive expected forward return
BEFORE building strategy logic on top.

Outputs t-stat, % directional, avg return at multiple horizons.
Threshold for "real signal": |t| > 2.0 with N >= 50 events.

Usage:
    python backtesting/scripts/signal_diagnostic.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtesting.engine.data import load_data

PAIRS = ["EURUSD", "GBPAUD", "GBPJPY", "GBPUSD", "EURGBP", "GBPCAD", "AUDUSD"]
TFS   = ["5", "15"]
START = "2026-01-01"
END   = "2026-05-23"

# Forward return horizons in bars
HORIZONS = [4, 8, 16, 32]  # on 5m: 20m/40m/80m/160m; on 15m: 1h/2h/4h/8h


# ── helpers ──────────────────────────────────────────────────────────────────

def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _roll_range(df: pd.DataFrame, lookback: int) -> pd.Series:
    return df["high"].rolling(lookback).max() - df["low"].rolling(lookback).min()


def _forward_return(df: pd.DataFrame, i: int, direction: int, h: int) -> float:
    """Signed forward return at horizon h bars. direction: +1 long, -1 short."""
    j = i + h
    if j >= len(df):
        return float("nan")
    entry = float(df["close"].iloc[i])
    future = float(df["close"].iloc[j])
    return direction * (future - entry) / entry


def _tstat(arr: np.ndarray) -> float:
    arr = arr[~np.isnan(arr)]
    if len(arr) < 5 or arr.std(ddof=1) == 0:
        return 0.0
    return float(arr.mean() / (arr.std(ddof=1) / np.sqrt(len(arr))))


# ── signal detectors ─────────────────────────────────────────────────────────

def detect_accumulation_sweeps(
    df: pd.DataFrame,
    lookback: int = 20,
    history_bars: int = 50,
    compress_ratio: float = 0.70,
) -> pd.DataFrame:
    """Range-compressed + wick sweep signal."""
    rr = _roll_range(df, lookback)
    mean_rr = rr.rolling(history_bars).mean()
    events = []
    min_i = lookback + history_bars
    for i in range(min_i, len(df)):
        cur_range = float(rr.iloc[i - 1])
        mean_r = float(mean_rr.iloc[i - 1])
        if np.isnan(cur_range) or np.isnan(mean_r) or mean_r == 0:
            continue
        if cur_range >= compress_ratio * mean_r:
            continue  # not compressed

        win = df.iloc[i - lookback: i]
        rh = float(win["high"].max())
        rl = float(win["low"].min())
        bar = df.iloc[i]

        if bar["low"] < rl and bar["close"] > rl:
            events.append({"i": i, "direction": +1, "signal": "acc_bull_sweep"})
        elif bar["high"] > rh and bar["close"] < rh:
            events.append({"i": i, "direction": -1, "signal": "acc_bear_sweep"})

    return pd.DataFrame(events) if events else pd.DataFrame(columns=["i", "direction", "signal"])


def detect_bos(
    df: pd.DataFrame,
    lookback: int = 20,
) -> pd.DataFrame:
    """Break-of-structure signal (close beyond N-bar high/low)."""
    events = []
    for i in range(lookback, len(df)):
        win = df.iloc[i - lookback: i]
        prior_high = float(win["high"].max())
        prior_low = float(win["low"].min())
        bar = df.iloc[i]

        if bar["close"] > prior_high:
            events.append({"i": i, "direction": +1, "signal": "bos_bull"})
        elif bar["close"] < prior_low:
            events.append({"i": i, "direction": -1, "signal": "bos_bear"})

    return pd.DataFrame(events) if events else pd.DataFrame(columns=["i", "direction", "signal"])


# ── analysis ─────────────────────────────────────────────────────────────────

def analyze(df: pd.DataFrame, events: pd.DataFrame, horizons: list[int]) -> list[dict]:
    if events.empty:
        return []
    rows = []
    signal_groups = events.groupby("signal")
    for sig, grp in signal_groups:
        direction = int(grp["direction"].iloc[0])
        result = {"signal": sig, "N": len(grp)}
        for h in horizons:
            rets = np.array([_forward_return(df, int(r["i"]), r["direction"], h)
                             for _, r in grp.iterrows()])
            rets = rets[~np.isnan(rets)]
            result[f"avg_ret_{h}b"] = round(float(np.mean(rets)) * 1e4, 3) if len(rets) else 0  # in pips * 10000
            result[f"pct_pos_{h}b"] = round(float(np.mean(rets > 0)) * 100, 1) if len(rets) else 0
            result[f"t_{h}b"] = round(_tstat(rets), 2)
        rows.append(result)
    return rows


# ── main ──────────────────────────────────────────────────────────────────────

def run_pair(pair: str, tf: str) -> list[dict]:
    df = load_data(pair, tf=tf, start=START, end=END)
    if df.empty:
        return []
    if "ts" in df.columns:
        df = df.set_index("ts")
    df = df.sort_index().reset_index(drop=False)

    rows = []
    # TR Accumulation
    for compress in [0.65, 0.75]:
        events = detect_accumulation_sweeps(df, lookback=20, compress_ratio=compress)
        for r in analyze(df, events, HORIZONS):
            r.update(pair=pair, tf=tf, params=f"compress={compress}")
            rows.append(r)

    # TR Breakout
    for lb in [15, 20]:
        events = detect_bos(df, lookback=lb)
        for r in analyze(df, events, HORIZONS):
            r.update(pair=pair, tf=tf, params=f"bos_lb={lb}")
            rows.append(r)

    return rows


def main():
    all_rows = []
    for pair in PAIRS:
        for tf in TFS:
            print(f"  {pair} {tf}m ...", end=" ", flush=True)
            rows = run_pair(pair, tf)
            all_rows.extend(rows)
            print(f"{len(rows)} signals")

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("No events detected.")
        return

    # Key horizon: 8 bars
    h = 8
    t_col = f"t_{h}b"
    pct_col = f"pct_pos_{h}b"
    ret_col = f"avg_ret_{h}b"

    print("\n" + "="*90)
    print(f"TOP SIGNALS by |t| at {h}-bar horizon (threshold: |t|>2.0, N>=50)")
    print("="*90)
    display = df[df["N"] >= 30].copy()
    display["abs_t"] = display[t_col].abs()
    display = display.sort_values("abs_t", ascending=False)
    cols = ["pair", "tf", "signal", "params", "N", t_col, pct_col, ret_col]
    print(display[cols].head(20).to_string(index=False))

    print("\n" + "="*90)
    print("FULL TABLE (all signals, sorted by t-stat at 8-bar horizon)")
    print("="*90)
    out_cols = ["pair", "tf", "signal", "params", "N"] + \
               [f"t_{h}b" for h in HORIZONS] + \
               [f"pct_pos_{h}b" for h in HORIZONS]
    print(df.sort_values(t_col, ascending=False)[out_cols].to_string(index=False))


if __name__ == "__main__":
    main()
