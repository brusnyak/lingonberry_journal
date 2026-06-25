#!/usr/bin/env python3
"""
Comprehensive price pattern research across all forex pairs and timeframes.

Tests:
  1. Accumulation sweep (Asian range + London sweep) — with/without killzone filter
  2. BOS Fade (SHORT after bullish BOS, LONG after bearish BOS)
  3. FVG fill (3-bar imbalance)
  4. PDH/PDL sweep + reversal

For each signal: t-stat at 8 and 16 bar horizons, % directional, N events.
Target: identify signals with |t| > 2.5, N >= 50, stable across multiple pairs.

"Next 15 candles" accuracy = pct_pos at 16-bar horizon on 15m (= next 4 hours).

Usage:
    python backtesting/scripts/pattern_research.py
    python backtesting/scripts/pattern_research.py --tf 15 --pair EURUSD
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backtesting.engine.data import load_data

# ── config ────────────────────────────────────────────────────────────────────

PAIRS = ["EURUSD", "GBPAUD", "GBPJPY", "GBPUSD", "EURGBP", "GBPCAD", "AUDUSD"]
TFS = ["5", "15"]

# Full IS data (before OOS starts)
IS_START = "2022-07-01"
IS_END   = "2026-05-23"

HORIZONS = [8, 16, 32]  # bars; on 15m: 2h / 4h / 8h; on 5m: 40m / 80m / 160m

# Killzone windows — in UTC hours (24h)
# Note: data timestamps are UTC; forex broker days end ~22 UTC
KILLZONES = {
    "all":    (0, 24),      # no filter
    "asian":  (22, 3),      # 22:00–03:00 UTC (7pm–10pm ET accumulation)
    "london": (6, 10),      # 06:00–10:00 UTC (2am–6am ET)
    "ny":     (13, 17),     # 13:00–17:00 UTC (9am–1pm ET)
    "off":    (10, 13),     # dead zone between London and NY
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _hour_in_zone(hour: int, start_h: int, end_h: int) -> bool:
    """True if UTC hour is within the killzone (handles midnight wrap)."""
    if start_h <= end_h:
        return start_h <= hour < end_h
    else:  # wraps midnight e.g. 22–03
        return hour >= start_h or hour < end_h


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _roll_range(df: pd.DataFrame, lookback: int) -> pd.Series:
    return df["high"].rolling(lookback).max() - df["low"].rolling(lookback).min()


def _forward_return(df: pd.DataFrame, i: int, direction: int, h: int) -> float:
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


def _hour_arr(df: pd.DataFrame) -> np.ndarray:
    """Extract UTC hour for each row (handles tz-aware and naive)."""
    ts = df["ts"] if "ts" in df.columns else df.index
    if hasattr(ts, "dt"):
        return ts.dt.hour.to_numpy()
    return np.array([t.hour for t in ts])


def _htf_direction(df4h: pd.DataFrame) -> pd.Series:
    """
    Return a Series indexed by 4H bar position:
    +1 = bullish bias (last close > last close N bars ago)
    -1 = bearish bias
     0 = neutral
    """
    if df4h is None or df4h.empty:
        return None
    c = df4h["close"]
    # Bias = direction of last 10-bar price change on 4H (~2 days)
    delta = c - c.shift(10)
    direction = np.sign(delta)
    return direction


# ── pattern detectors ─────────────────────────────────────────────────────────

def detect_acc_sweep(
    df: pd.DataFrame,
    lookback: int = 20,
    history_bars: int = 50,
    compress_ratio: float = 0.70,
    killzone: str = "all",
    htf_dir: np.ndarray | None = None,   # +1/-1 per bar (aligned to df index)
) -> pd.DataFrame:
    """
    Accumulation sweep: range-compressed + wick beyond range + close back inside.
    killzone: one of KILLZONES keys to restrict signal to specific session.
    htf_dir: if provided, only take signals where htf agrees with direction.
    """
    hours = _hour_arr(df)
    kz_start, kz_end = KILLZONES[killzone]

    rr = _roll_range(df, lookback)
    mean_rr = rr.rolling(history_bars).mean()
    min_i = lookback + history_bars

    events = []
    for i in range(min_i, len(df)):
        # Killzone filter
        if killzone != "all" and not _hour_in_zone(int(hours[i]), kz_start, kz_end):
            continue

        cur_range = float(rr.iloc[i - 1])
        mean_r = float(mean_rr.iloc[i - 1])
        if np.isnan(cur_range) or np.isnan(mean_r) or mean_r == 0:
            continue
        if cur_range >= compress_ratio * mean_r:
            continue

        win = df.iloc[i - lookback: i]
        rh = float(win["high"].max())
        rl = float(win["low"].min())
        bar = df.iloc[i]

        if bar["low"] < rl and bar["close"] > rl:
            direction = +1
            signal = "acc_bull_sweep"
        elif bar["high"] > rh and bar["close"] < rh:
            direction = -1
            signal = "acc_bear_sweep"
        else:
            continue

        # HTF direction agreement
        if htf_dir is not None and htf_dir[i] != 0 and htf_dir[i] != direction:
            continue

        events.append({"i": i, "direction": direction, "signal": signal})

    return pd.DataFrame(events) if events else pd.DataFrame(columns=["i", "direction", "signal"])


def detect_bos_fade(
    df: pd.DataFrame,
    lookback: int = 20,
    killzone: str = "all",
) -> pd.DataFrame:
    """
    BOS FADE: short after bullish BOS, long after bearish BOS.
    (Signal direction is OPPOSITE to BOS direction — fade the breakout.)
    """
    hours = _hour_arr(df)
    kz_start, kz_end = KILLZONES[killzone]

    events = []
    for i in range(lookback, len(df)):
        if killzone != "all" and not _hour_in_zone(int(hours[i]), kz_start, kz_end):
            continue

        win = df.iloc[i - lookback: i]
        prior_high = float(win["high"].max())
        prior_low  = float(win["low"].min())
        bar = df.iloc[i]

        if bar["close"] > prior_high:
            # Bullish BOS → fade = SHORT
            events.append({"i": i, "direction": -1, "signal": "bos_fade_bear"})
        elif bar["close"] < prior_low:
            # Bearish BOS → fade = LONG
            events.append({"i": i, "direction": +1, "signal": "bos_fade_bull"})

    return pd.DataFrame(events) if events else pd.DataFrame(columns=["i", "direction", "signal"])


def detect_fvg(
    df: pd.DataFrame,
    min_fvg_atr_pct: float = 0.3,
    killzone: str = "all",
) -> pd.DataFrame:
    """
    Fair Value Gap: 3-bar imbalance.
    Bullish FVG: bar[i].low > bar[i-2].high → fill = LONG toward gap.
    Bearish FVG: bar[i].high < bar[i-2].low → fill = SHORT toward gap.
    Entry on NEXT bar (bar after FVG forms), measuring forward return.
    min_fvg_atr_pct: FVG must be at least this fraction of ATR14 to count.
    """
    hours = _hour_arr(df)
    kz_start, kz_end = KILLZONES[killzone]
    atr14 = _atr(df, 14)

    events = []
    for i in range(3, len(df) - 1):
        if killzone != "all" and not _hour_in_zone(int(hours[i]), kz_start, kz_end):
            continue

        gap_size_thresh = float(atr14.iloc[i]) * min_fvg_atr_pct
        if np.isnan(gap_size_thresh) or gap_size_thresh <= 0:
            continue

        b0 = df.iloc[i]       # current bar
        b2 = df.iloc[i - 2]   # 2 bars ago

        # Bullish FVG: gap above (b2.high → b0.low) — price fills downward to b0.low
        if b0["low"] > b2["high"]:
            gap_size = b0["low"] - b2["high"]
            if gap_size >= gap_size_thresh:
                # We LONG because price will pull back to fill the gap (fill = drop = SHORT? No)
                # The gap is above: bar[i-2] high < bar[i] low → unfilled bullish gap
                # Filling means price comes BACK DOWN to the gap → SHORT toward fill
                events.append({"i": i + 1, "direction": -1, "signal": "fvg_bull_fill"})

        # Bearish FVG: gap below (b0.high < b2.low) — price fills upward
        elif b0["high"] < b2["low"]:
            gap_size = b2["low"] - b0["high"]
            if gap_size >= gap_size_thresh:
                events.append({"i": i + 1, "direction": +1, "signal": "fvg_bear_fill"})

    return pd.DataFrame(events) if events else pd.DataFrame(columns=["i", "direction", "signal"])


def detect_pdhl_sweep(
    df: pd.DataFrame,
    killzone: str = "all",
) -> pd.DataFrame:
    """
    Previous Day High/Low sweep + rejection.
    Sweep of PDH (wick above, close below) → LONG (price rejected upper level).
    Sweep of PDL (wick below, close above) → SHORT (price rejected lower level).
    Wait — standard PDH/PDL sweep:
      PDH sweep: bar.high > prev_day_high AND bar.close < prev_day_high → SHORT
      PDL sweep: bar.low < prev_day_low AND bar.close > prev_day_low  → LONG
    Uses daily candles to get PDH/PDL, then fires on intraday bars.
    """
    hours = _hour_arr(df)
    kz_start, kz_end = KILLZONES[killzone]

    # Build daily high/low lookup
    ts_col = df["ts"] if "ts" in df.columns else df.index.to_series()
    if hasattr(ts_col, "dt"):
        dates = ts_col.dt.date.to_numpy()
    else:
        dates = np.array([t.date() for t in ts_col])

    # Daily OHLC
    df_copy = df.copy()
    df_copy["_date"] = dates
    daily = df_copy.groupby("_date").agg(
        daily_high=("high", "max"),
        daily_low=("low", "min"),
    ).reset_index()
    daily = daily.sort_values("_date").reset_index(drop=True)

    # Build date → (prev_high, prev_low) map
    prev_map = {}
    for idx in range(1, len(daily)):
        d = daily.loc[idx, "_date"]
        prev_map[d] = (
            float(daily.loc[idx - 1, "daily_high"]),
            float(daily.loc[idx - 1, "daily_low"]),
        )

    events = []
    for i in range(len(df)):
        if killzone != "all" and not _hour_in_zone(int(hours[i]), kz_start, kz_end):
            continue

        d = dates[i]
        if d not in prev_map:
            continue

        pdh, pdl = prev_map[d]
        bar = df.iloc[i]

        if bar["high"] > pdh and bar["close"] < pdh:
            events.append({"i": i, "direction": -1, "signal": "pdh_sweep_short"})
        elif bar["low"] < pdl and bar["close"] > pdl:
            events.append({"i": i, "direction": +1, "signal": "pdl_sweep_long"})

    return pd.DataFrame(events) if events else pd.DataFrame(columns=["i", "direction", "signal"])


# ── analysis ──────────────────────────────────────────────────────────────────

def analyze(df: pd.DataFrame, events: pd.DataFrame, horizons: list[int]) -> list[dict]:
    if events.empty:
        return []
    rows = []
    for sig, grp in events.groupby("signal"):
        result = {"signal": sig, "N": len(grp)}
        for h in horizons:
            rets = np.array([
                _forward_return(df, int(r["i"]), int(r["direction"]), h)
                for _, r in grp.iterrows()
            ])
            rets = rets[~np.isnan(rets)]
            n = len(rets)
            result[f"t_{h}b"]       = round(_tstat(rets), 2) if n >= 5 else 0
            result[f"pct_pos_{h}b"] = round(float(np.mean(rets > 0)) * 100, 1) if n else 0
            result[f"avg_r_{h}b"]   = round(float(np.mean(rets)) * 1e4, 1) if n else 0  # ×10000 = rough pips×10
        rows.append(result)
    return rows


# ── per-pair runner ───────────────────────────────────────────────────────────

def run_pair(pair: str, tf: str) -> list[dict]:
    df = load_data(pair, tf=tf, start=IS_START, end=IS_END)
    if df.empty:
        return []
    if "ts" in df.columns:
        df = df.set_index("ts")
    df = df.sort_index().reset_index(drop=False)

    # 4H data for HTF direction
    df4h = load_data(pair, tf="240", start=IS_START, end=IS_END)
    htf_dir_aligned = None
    if not df4h.empty:
        df4h = df4h.set_index("ts").sort_index()
        dir4h = _htf_direction(df4h)
        ts_entry = df["ts"].to_numpy()
        ts_4h = dir4h.index.to_numpy()
        dir4h_vals = dir4h.to_numpy()
        # Align: for each entry bar, find the most recent 4H bar
        idx4h = np.searchsorted(ts_4h, ts_entry, side="right") - 1
        htf_dir_aligned = np.where(idx4h >= 0, dir4h_vals[np.clip(idx4h, 0, len(dir4h_vals)-1)], 0)

    rows = []

    # 1. Accumulation sweeps — multiple killzone conditions
    for kz in ["all", "london", "ny", "asian"]:
        events = detect_acc_sweep(df, lookback=20, compress_ratio=0.70, killzone=kz)
        for r in analyze(df, events, HORIZONS):
            r.update(pair=pair, tf=tf, pattern="acc_sweep", filter=kz, htf="any")
            rows.append(r)

    # 2. Acc sweep with HTF direction agreement (London only, most relevant killzone)
    if htf_dir_aligned is not None:
        for kz in ["london", "all"]:
            events = detect_acc_sweep(df, lookback=20, compress_ratio=0.70,
                                      killzone=kz, htf_dir=htf_dir_aligned)
            for r in analyze(df, events, HORIZONS):
                r.update(pair=pair, tf=tf, pattern="acc_sweep", filter=kz, htf="4h_agree")
                rows.append(r)

    # 3. BOS Fade
    for kz in ["all", "london", "ny"]:
        events = detect_bos_fade(df, lookback=20, killzone=kz)
        for r in analyze(df, events, HORIZONS):
            r.update(pair=pair, tf=tf, pattern="bos_fade", filter=kz, htf="any")
            rows.append(r)

    # 4. FVG fill
    events = detect_fvg(df, min_fvg_atr_pct=0.3)
    for r in analyze(df, events, HORIZONS):
        r.update(pair=pair, tf=tf, pattern="fvg", filter="all", htf="any")
        rows.append(r)

    # 5. PDH/PDL sweep (London + NY most relevant)
    for kz in ["all", "london", "ny"]:
        events = detect_pdhl_sweep(df, killzone=kz)
        for r in analyze(df, events, HORIZONS):
            r.update(pair=pair, tf=tf, pattern="pdhl_sweep", filter=kz, htf="any")
            rows.append(r)

    return rows


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tf", default=None, help="Run only this TF (5 or 15)")
    parser.add_argument("--pair", default=None, help="Run only this pair")
    parser.add_argument("--min-n", type=int, default=50, help="Min events to show")
    parser.add_argument("--horizon", type=int, default=16, help="Primary horizon in bars")
    args = parser.parse_args()

    pairs = [args.pair] if args.pair else PAIRS
    tfs   = [args.tf]   if args.tf   else TFS

    all_rows = []
    for pair in pairs:
        for tf in tfs:
            print(f"  {pair} {tf}m ...", end=" ", flush=True)
            rows = run_pair(pair, tf)
            all_rows.extend(rows)
            print(f"{len(rows)} signal rows")

    if not all_rows:
        print("No data found.")
        return

    df = pd.DataFrame(all_rows)
    h = args.horizon
    t_col  = f"t_{h}b"
    p_col  = f"pct_pos_{h}b"
    r_col  = f"avg_r_{h}b"

    # ── Cross-pair aggregation ─────────────────────────────────────────────
    print("\n" + "=" * 100)
    print(f"CROSS-PAIR SIGNAL SUMMARY  |  horizon={h}-bar  |  min_N={args.min_n}")
    print(f"{'pattern':<14} {'filter':<10} {'htf':<10} {'tf':>3}  "
          f"{'pairs_pos':>10}  {'avg_t':>7}  {'avg_pct':>8}  {'total_N':>8}")
    print("=" * 100)

    # Aggregate: for each (pattern, filter, htf, tf, signal) across pairs
    agg_key = ["pattern", "filter", "htf", "tf", "signal"]
    grouped = df[df["N"] >= args.min_n].groupby(agg_key)
    agg_rows = []
    for key, grp in grouped:
        agg_rows.append({
            "pattern":    key[0],
            "filter":     key[1],
            "htf":        key[2],
            "tf":         key[3],
            "signal":     key[4],
            "pairs":      len(grp),
            "pairs_pos":  int((grp[t_col] > 0).sum()),
            "avg_t":      round(float(grp[t_col].mean()), 2),
            "avg_pct":    round(float(grp[p_col].mean()), 1),
            "total_N":    int(grp["N"].sum()),
        })

    if agg_rows:
        agg_df = pd.DataFrame(agg_rows)
        agg_df = agg_df.sort_values("avg_t", ascending=False)
        for _, row in agg_df.head(30).iterrows():
            print(f"{row['pattern']:<14} {row['filter']:<10} {row['htf']:<10} {row['tf']:>3}  "
                  f"  {row['pairs_pos']}/{row['pairs']:>2} pairs  "
                  f"{row['avg_t']:>+7.2f}  {row['avg_pct']:>7.1f}%  {row['total_N']:>8,}")

    # ── Detail table: best signals per pair ───────────────────────────────
    print("\n" + "=" * 100)
    print(f"TOP SIGNALS PER PAIR  (|t| at {h}-bar horizon, N >= {args.min_n})")
    print("=" * 100)

    detail = df[df["N"] >= args.min_n].copy()
    detail["abs_t"] = detail[t_col].abs()
    detail = detail.sort_values(["pair", "abs_t"], ascending=[True, False])

    cols = ["pair", "tf", "signal", "pattern", "filter", "htf", "N", t_col, p_col, r_col]
    available_cols = [c for c in cols if c in detail.columns]
    print(detail.groupby("pair").head(3)[available_cols].to_string(index=False))

    # ── Killzone comparison for acc_sweep on EURUSD ───────────────────────
    print("\n" + "=" * 100)
    print(f"KILLZONE EFFECT on acc_sweep (all pairs, 15m, no HTF filter)")
    print("=" * 100)

    kz_df = df[
        (df["pattern"] == "acc_sweep") &
        (df["tf"] == "15") &
        (df["htf"] == "any")
    ].copy()
    if not kz_df.empty:
        kz_agg = kz_df.groupby(["filter", "signal"]).agg(
            pairs_with_edge=(t_col, lambda x: (x > 1.5).sum()),
            avg_t=(t_col, "mean"),
            avg_pct=(p_col, "mean"),
            total_N=("N", "sum"),
            avg_N=("N", "mean"),
        ).round(2).reset_index()
        kz_agg = kz_agg.sort_values("avg_t", ascending=False)
        print(kz_agg.to_string(index=False))

    # ── Save results ──────────────────────────────────────────────────────
    out_path = ROOT / "backtesting" / "results" / "pattern_research.csv"
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"\nFull results saved → {out_path}")


if __name__ == "__main__":
    main()
