#!/usr/bin/env python3
"""
Rolling window validation for the best strategy config.

⚠ This file depends on strategy_v2.py which was removed during the
  engine refactor. It needs to be re-imported once a new strategy
  interface is built. See backtesting/engine/ for the new architecture.

Usage (stale):
    python backtesting/rolling_analysis.py
"""
from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

_SCRIPT = Path(__file__).parent
_ROOT   = _SCRIPT.parent
sys.path = [p for p in sys.path if p != str(_SCRIPT)]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

warnings.filterwarnings("ignore")

# strategy_v2.py no longer exists — uncomment when strategy engine is rebuilt:
# from backtesting.strategy_v2 import (
#     Config, add_indicators, backtest, build_15m_state,
#     load_window, metrics, pip_size,
# )

DATA_DIR = _ROOT / "data" / "market_data"


# Configs to validate — name → Config overrides
ROLL_CONFIGS = {
    "m15t_kz_bos_long_partial":  dict(killzone=True, m15_bos=True, direction="long",
                                       exit_mode="partial", rr=1.5),
    "m15t_kz_bos_both_partial":  dict(killzone=True, m15_bos=True, direction="both",
                                       exit_mode="partial", rr=1.5),
    "m15t_kz_bos_long_rr2":      dict(killzone=True, m15_bos=True, direction="long",
                                       exit_mode="rr",      rr=2.0),
    "m15t_bos_long_partial":     dict(m15_bos=True,            direction="long",
                                       exit_mode="partial", rr=1.5),
    "m15t_kz_long_partial":      dict(killzone=True,            direction="long",
                                       exit_mode="partial", rr=1.5),
}


def prepare_full(pair: str) -> tuple[pd.DataFrame, list]:
    """Load, indicator-enrich, and compute 15m state for the full dataset."""
    f = DATA_DIR / f"{pair}1.csv"
    df = pd.read_csv(f, sep="\t", header=None,
                     names=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_localize("UTC")
    df = df.sort_values("ts").set_index("ts").astype(float)
    df = add_indicators(df)
    df, fvgs = build_15m_state(df)
    return df, fvgs


def rolling_windows(df: pd.DataFrame, window_days: int, step_days: int):
    """Yield (label, start, end, slice_df) for each rolling window."""
    first = df.index[0].normalize()
    last  = df.index[-1].normalize()
    start = first
    while start + pd.Timedelta(days=window_days) <= last + pd.Timedelta(days=1):
        end  = start + pd.Timedelta(days=window_days)
        slug = f"{start.strftime('%b%d')}–{end.strftime('%b%d')}"
        chunk = df[(df.index >= start) & (df.index < end)]
        if len(chunk) > 500:  # skip windows with too little data
            yield slug, start, end, chunk
        start += pd.Timedelta(days=step_days)


def run_rolling(pairs: list[str], window_days: int = 30, step_days: int = 15) -> pd.DataFrame:
    rows = []

    for pair in pairs:
        print(f"\n── {pair} ─────────────────────────────────", flush=True)
        t0  = time.time()
        df_full, fvgs = prepare_full(pair)
        is_jpy = "JPY" in pair
        ps     = pip_size(pair)
        print(f"  Loaded {len(df_full):,} bars  ({time.time()-t0:.1f}s)", flush=True)

        windows = list(rolling_windows(df_full, window_days, step_days))
        print(f"  {len(windows)} windows × {len(ROLL_CONFIGS)} configs", flush=True)

        for cfg_name, overrides in ROLL_CONFIGS.items():
            cfg = Config(**overrides)
            for win_label, win_start, win_end, chunk in windows:
                # Slice FVGs to those that start before this window ends
                win_fvgs = [f for f in fvgs if f.c2_time < win_end]
                m = metrics(backtest(chunk, cfg, win_fvgs, is_jpy, ps))
                rows.append(dict(
                    pair=pair, cfg=cfg_name, window=win_label,
                    win_start=win_start.date(), win_end=win_end.date(),
                    **m,
                ))
                print(
                    f"  {pair} {cfg_name:<35} {win_label:<14} | "
                    f"n={m['n']:>3}  wr={m['wr']:.0%}  "
                    f"ret={m['ret']:>6.1f}%  dd={m['dd']:.1f}%  "
                    f"mfe={m['avg_mfe']:.2f}R",
                    flush=True,
                )

    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame) -> None:
    if df.empty:
        print("No results.")
        return

    print(f"\n{'='*120}")
    print("ROLLING WINDOW SUMMARY — consistency check")
    print("=" * 120)

    for cfg_name, grp in df.groupby("cfg"):
        print(f"\n  Config: {cfg_name}")
        print(f"  {'pair':<10} {'windows':>7} {'WR mean':>8} {'WR min':>8} "
              f"{'ret mean':>9} {'DD mean':>8} {'profitable%':>12}")
        for pair, pg in grp.groupby("pair"):
            pg_v = pg[pg["n"] >= 5]  # only windows with ≥5 trades
            if pg_v.empty:
                continue
            print(f"  {pair:<10} {len(pg_v):>7} {pg_v['wr'].mean():>8.0%} "
                  f"{pg_v['wr'].min():>8.0%} "
                  f"{pg_v['ret'].mean():>9.1f}% "
                  f"{pg_v['dd'].mean():>8.1f}% "
                  f"{(pg_v['ret'] > 0).mean():>11.0%}")

    print(f"\n{'='*120}")
    print("BEST WINDOWS (wr ≥ 55%, n ≥ 10, dd < 10%)")
    print("=" * 120)
    best = df[(df["wr"] >= 0.55) & (df["n"] >= 10) & (df["dd"] < 10)]
    if best.empty:
        print("  (none)")
    else:
        cols = ["pair", "cfg", "window", "n", "wr", "ret", "dd", "avg_mfe"]
        print(best[cols].sort_values("wr", ascending=False).to_string(index=False))

    print(f"\n{'='*120}")
    print("WORST WINDOWS (ret < 0, n ≥ 5)")
    print("=" * 120)
    worst = df[(df["ret"] < 0) & (df["n"] >= 5)]
    if worst.empty:
        print("  (none — all windows profitable!)")
    else:
        cols = ["pair", "cfg", "window", "n", "wr", "ret", "dd"]
        print(worst[cols].sort_values("ret").to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs",   default="AUDCHF,GBPCHF,GBPAUD")
    parser.add_argument("--window",  type=int, default=30, help="Window size in days")
    parser.add_argument("--step",    type=int, default=15, help="Step between windows in days")
    parser.add_argument("--configs", default="",
                        help="Comma-separated config names to test (default: all)")
    args  = parser.parse_args()
    pairs = [p.strip().upper() for p in args.pairs.split(",")]

    if args.configs:
        keep = {c.strip() for c in args.configs.split(",")}
        filtered = {k: v for k, v in ROLL_CONFIGS.items() if k in keep}
        if filtered:
            ROLL_CONFIGS.clear()
            ROLL_CONFIGS.update(filtered)

    results = run_rolling(pairs=pairs, window_days=args.window, step_days=args.step)

    summarise(results)

    out = _ROOT / "backtesting" / "results" / "rolling_analysis.csv"
    out.parent.mkdir(exist_ok=True)
    results.to_csv(out, index=False)
    print(f"\nFull results → {out}")
