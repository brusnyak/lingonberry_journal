#!/usr/bin/env python3
"""Rolling-window stability for strict ICT direction events."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.scripts.ict_direction_accuracy import run_symbol, summarize  # noqa: E402

OUT = ROOT / "backtesting" / "results"
OUT.mkdir(parents=True, exist_ok=True)


def rolling_windows(events: pd.DataFrame, window_days: int, step_days: int, min_n: int) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    events = events.copy()
    events["ts"] = pd.to_datetime(events["ts"], utc=True)
    start = events["ts"].min().floor("D")
    end = events["ts"].max().ceil("D")
    rows = []
    cur = start
    while cur + pd.Timedelta(days=window_days) <= end:
        nxt = cur + pd.Timedelta(days=window_days)
        win = events[(events["ts"] >= cur) & (events["ts"] < nxt)]
        if not win.empty:
            summary = summarize(win, min_n=min_n)
            for row in summary.to_dict("records"):
                row["window_start"] = cur
                row["window_end"] = nxt
                rows.append(row)
        cur += pd.Timedelta(days=step_days)
    return pd.DataFrame(rows)


def aggregate_stability(rolling: pd.DataFrame, target: str, min_windows: int) -> pd.DataFrame:
    if rolling.empty:
        return pd.DataFrame()
    exp_col = f"exp_{target}"
    hit_col = f"hit_{target}_pct"
    keys = ["symbol", "predictor", "direction", "session"]
    rows = []
    for key, group in rolling.groupby(keys):
        if len(group) < min_windows:
            continue
        rows.append(
            {
                **dict(zip(keys, key)),
                "windows": len(group),
                "positive_windows": int((group[exp_col] > 0).sum()),
                "positive_window_pct": float((group[exp_col] > 0).mean() * 100.0),
                "avg_n": float(group["n"].mean()),
                f"avg_{hit_col}": float(group[hit_col].mean()),
                f"median_{exp_col}": float(group[exp_col].median()),
                f"worst_{exp_col}": float(group[exp_col].min()),
                f"best_{exp_col}": float(group[exp_col].max()),
                "avg_mfe_med_r": float(group["mfe_med_r"].mean()),
                "avg_mae_med_r": float(group["mae_med_r"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(
        [f"median_{exp_col}", "positive_window_pct", f"worst_{exp_col}", "avg_n"],
        ascending=[False, False, False, False],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rolling strict ICT direction stability")
    parser.add_argument("--symbols", default="XAUUSD,NAS100,GBPJPY,GBPUSD,EURUSD,GBPAUD")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--tf", default="5")
    parser.add_argument("--left", type=int, default=3)
    parser.add_argument("--right", type=int, default=3)
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--state-stride", type=int, default=12)
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=15)
    parser.add_argument("--min-n", type=int, default=5)
    parser.add_argument("--min-windows", type=int, default=4)
    parser.add_argument("--target", choices=["1r", "1.5r", "2r"], default="1r")
    parser.add_argument("--tag", default="ict_direction_rolling")
    args = parser.parse_args()

    frames = []
    for symbol in [s.strip().upper() for s in args.symbols.split(",") if s.strip()]:
        print(f"{symbol}...", flush=True)
        frame = run_symbol(symbol, args.days, args.tf, args.left, args.right, args.horizon, args.state_stride)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        raise SystemExit("No strict ICT direction events generated")

    events = pd.concat(frames, ignore_index=True)
    rolling = rolling_windows(events, args.window_days, args.step_days, args.min_n)
    stability = aggregate_stability(rolling, args.target, args.min_windows)

    events_path = OUT / f"{args.tag}_events.csv"
    rolling_path = OUT / f"{args.tag}_windows.csv"
    stability_path = OUT / f"{args.tag}_stability.csv"
    events.to_csv(events_path, index=False)
    rolling.to_csv(rolling_path, index=False)
    stability.to_csv(stability_path, index=False)
    print(f"Saved {stability_path} rows={len(stability)}")
    print(f"Saved {rolling_path} rows={len(rolling)}")
    print(f"Saved {events_path} rows={len(events)}")

    if not stability.empty:
        exp_col = f"exp_{args.target}"
        hit_col = f"hit_{args.target}_pct"
        cols = [
            "symbol",
            "predictor",
            "direction",
            "session",
            "windows",
            "positive_windows",
            "positive_window_pct",
            "avg_n",
            f"avg_{hit_col}",
            f"median_{exp_col}",
            f"worst_{exp_col}",
            "avg_mfe_med_r",
            "avg_mae_med_r",
        ]
        print(stability[cols].head(40).to_string(index=False))


if __name__ == "__main__":
    main()
