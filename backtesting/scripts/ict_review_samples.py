#!/usr/bin/env python3
"""Export strict ICT direction events for visual review."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "backtesting" / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export ICT events for review UI/manual chart audit.")
    parser.add_argument("--events", default=str(OUT / "ict_direction_rolling_180d_l3r3_events.csv"))
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--predictor", default="bearish_bos")
    parser.add_argument("--session", default="asia")
    parser.add_argument("--direction", default="short")
    parser.add_argument("--target", choices=["1r", "1.5r", "2r"], default="1.5r")
    parser.add_argument("--n", type=int, default=25)
    parser.add_argument("--tag", default="ict_review_samples")
    args = parser.parse_args()

    path = Path(args.events)
    if not path.exists():
        raise SystemExit(f"Missing events file: {path}")
    events = pd.read_csv(path)
    events["ts"] = pd.to_datetime(events["ts"], utc=True)
    filt = events[
        (events["symbol"].str.upper() == args.symbol.upper())
        & (events["predictor"] == args.predictor)
        & (events["session"] == args.session)
        & (events["direction"] == args.direction)
    ].copy()
    if filt.empty:
        raise SystemExit("No matching events")

    outcome = f"outcome_{args.target}"
    hit = f"hit_{args.target}"
    keep_cols = [
        "symbol",
        "ts",
        "predictor",
        "direction",
        "session",
        "risk_price",
        "mfe_r",
        "mae_r",
        "close_r",
        hit,
        outcome,
        "protected_low",
        "protected_high",
        "last_hl",
        "last_lh",
    ]
    winners = filt.sort_values(outcome, ascending=False).head(args.n).copy()
    losers = filt.sort_values(outcome, ascending=True).head(args.n).copy()
    sample = pd.concat(
        [
            winners.assign(review_bucket="best"),
            losers.assign(review_bucket="worst"),
        ],
        ignore_index=True,
    )
    sample = sample[["review_bucket", *keep_cols]]
    out_path = OUT / f"{args.tag}_{args.symbol.upper()}_{args.predictor}_{args.session}_{args.target}.csv"
    sample.to_csv(out_path, index=False)
    print(f"Saved {out_path} rows={len(sample)}")
    print(sample[["review_bucket", "symbol", "ts", "predictor", "session", "mfe_r", "mae_r", hit, outcome]].to_string(index=False))


if __name__ == "__main__":
    main()
