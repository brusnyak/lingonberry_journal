#!/usr/bin/env python3
"""Check that structure features are stable when computed online.

This catches lookahead bugs where a full-history structure label differs from
the label that would have been known after the same candle in live trading.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.engine.data import load_data  # noqa: E402
from backtesting.features.structure import StructureConfig, build_structure_index  # noqa: E402


CHECK_COLS = [
    "structure_label",
    "regime",
    "last_swing_high",
    "last_swing_low",
    "last_hh",
    "last_hl",
    "last_lh",
    "last_ll",
    "bos_up",
    "bos_down",
    "choch_up",
    "choch_down",
    "sweep_high",
    "sweep_low",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Structure online parity check")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--tf", default="5")
    parser.add_argument("--asset-type", default="commodity")
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--left", type=int, default=2)
    parser.add_argument("--right", type=int, default=2)
    parser.add_argument("--warmup-bars", type=int, default=300)
    parser.add_argument("--stride", type=int, default=25)
    parser.add_argument("--max-mismatches", type=int, default=0)
    args = parser.parse_args()

    df = load_data(args.symbol, args.tf, days=args.days, asset_type=args.asset_type)
    if df.empty:
        raise SystemExit(f"No data for {args.symbol} {args.tf}")
    cfg = StructureConfig(left=args.left, right=args.right)
    full = build_structure_index(df, cfg)

    rows = []
    checked = 0
    for i in range(max(args.warmup_bars, args.left + args.right + 5), len(df), args.stride):
        online = build_structure_index(df.iloc[: i + 1].copy(), cfg)
        f = full.iloc[i]
        o = online.iloc[-1]
        checked += 1
        diffs = {}
        for col in CHECK_COLS:
            fv = f[col]
            ov = o[col]
            if pd.isna(fv) and pd.isna(ov):
                continue
            if isinstance(fv, float) or isinstance(ov, float):
                if pd.isna(fv) != pd.isna(ov) or (not pd.isna(fv) and abs(float(fv) - float(ov)) > 1e-9):
                    diffs[col] = {"full": fv, "online": ov}
            elif fv != ov:
                diffs[col] = {"full": fv, "online": ov}
        if diffs:
            rows.append({"i": i, "ts": f["ts"], "diffs": diffs})

    out = pd.DataFrame(rows)
    print(f"symbol={args.symbol} tf={args.tf} bars={len(df)} checked={checked} mismatches={len(out)}")
    if not out.empty:
        print(out.head(20).to_string(index=False))
    if len(out) > args.max_mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
