#!/usr/bin/env python3
"""
Level 1 — Single-condition scanner.

Tests individual ICT/SMC conditions one at a time using rolling windows
and bootstrap statistics.

Usage:
    python -m hypothesis_engine.level1_conditions.run --quick
    python -m hypothesis_engine.level1_conditions.run --quick --conditions sweep,bos
    python -m hypothesis_engine.level1_conditions.run --full --csv results.csv
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hypothesis_engine.level1_conditions.scanner import run_rolling_all
from hypothesis_engine.level1_conditions.conditions import CONDITIONS


QUICK_PAIRS = [
    "EURUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD",
    "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "AUDJPY",
    "NZDUSD", "EURJPY", "EURGBP", "EURAUD", "EURCHF",
    "XAUUSD", "USATECHIDXUSD",
]
QUICK_TFS = ("5", "15", "60", "240")


def format_report(df) -> str:
    """Format aggregated condition results."""
    if df.empty:
        return "No results."

    lines = []
    lines.append("=" * 140)
    lines.append("LEVEL 1 — SINGLE CONDITION SCAN (Rolling Window)")
    lines.append("=" * 140)

    header = (
        f"{'Symbol':<10} {'TF':>3} {'Condition':<12} {'Signal':<6} "
        f"{'Session':<10} {'H':>2} {'Sig/All':>7} {'Stab':>5} "
        f"{'MeanRet':>9} {'t_avg':>7} {'WR':>6} {'PF':>6} {'Score':>5}"
    )
    lines.append(header)
    lines.append("-" * 140)

    top = df.head(40)
    for _, row in top.iterrows():
        sig = f"{int(row['n_significant'])}/{int(row['n_windows'])}"
        stab = f"{row['stability']:.0%}"
        lines.append(
            f"{row['symbol']:<10} {str(row['tf']):>3} {row['condition']:<12} "
            f"{row['signal_dir']:<6} {row['session']:<10} {int(row['horizon']):>2} "
            f"{sig:>7} {stab:>5} "
            f"{row['mean_mean_ret']:>+9.6f} {row['avg_t_stat']:>+7.2f} "
            f"{row['avg_wr']:>6.1%} {row['avg_pf']:>6.2f} "
            f"{row['score']:>5.2f}"
        )

    lines.append("-" * 140)
    lines.append(f"Total condition-pockets tracked: {len(df)}")
    lines.append(f"  Consistent (stability=100%): {(df['consistent']).sum()}")
    lines.append(f"  |t| > 2.0: {len(df[df['avg_t_stat'].abs() > 2])}")
    lines.append(f"  |t| > 2.0 AND stability>80%: {len(df[(df['avg_t_stat'].abs() > 2) & (df['stability'] > 0.80)])}")
    lines.append("=" * 140)

    # Best by condition
    lines.append("")
    lines.append("BEST PER CONDITION:")
    for cond in df['condition'].unique():
        best = df[df['condition'] == cond].head(3)
        if best.empty:
            continue
        lines.append(f"  {cond}:")
        for _, row in best.iterrows():
            lines.append(
                f"    {row['symbol']:<10} {str(row['tf']):>3}m {row['signal_dir']:<6} "
                f"{row['session']:<10} h={int(row['horizon']):>2} "
                f"mean={row['mean_mean_ret']:>+9.6f} t={row['avg_t_stat']:>+6.2f} "
                f"stab={row['stability']:.0%} wr={row['avg_wr']:>5.1%} pf={row['avg_pf']:>6.2f}"
            )

    lines.append("")
    lines.append("=" * 140)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Level 1 — Single Condition Scanner")
    parser.add_argument("--quick", action="store_true", help="Quick scan (17 pairs, 4 TFs)")
    parser.add_argument("--full", action="store_true", help="All forex pairs")
    parser.add_argument("--pairs", type=str, default="", help="Comma-separated override")
    parser.add_argument("--tfs", type=str, default="", help="Comma-separated TFs")
    parser.add_argument("--conditions", type=str, default="", help="Comma-separated (default: all)")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=15)
    parser.add_argument("--csv", type=str, default="", help="Export to CSV")
    parser.add_argument("--no-oos", action="store_true", help="Exclude OOS data")
    args = parser.parse_args()

    if args.pairs:
        pairs = [p.strip().upper() for p in args.pairs.split(",")]
    elif args.full:
        from backtesting.engine.data import list_pairs
        pairs = [p for p in list_pairs("forex") if p.isascii() and len(p) > 3 and not any(c.isdigit() for c in p)]
        pairs = sorted(set(pairs))[:30]
    else:
        pairs = QUICK_PAIRS

    tfs = tuple(t.strip() for t in args.tfs.split(",")) if args.tfs else QUICK_TFS
    conditions = [c.strip() for c in args.conditions.split(",")] if args.conditions else list(CONDITIONS.keys())

    print(f"Level 1 — Single Condition Scan")
    print(f"  Pairs: {len(pairs)}  TFs: {tfs}  Conditions: {conditions}")
    print(f"  Window: {args.window_days}d  Step: {args.step_days}d")
    print(f"  OOS: {'excluded' if args.no_oos else 'included'}")
    print(f"  Total runs: {len(pairs) * len(tfs) * len(conditions)}")
    print()

    t0 = time.time()
    df = run_rolling_all(
        symbols=pairs,
        tfs=tfs,
        conditions=conditions,
        window_days=args.window_days,
        step_days=args.step_days,
        allow_oos=not args.no_oos,
        verbose=True,
    )
    elapsed = time.time() - t0

    print()
    print(f"Completed in {elapsed:.1f}s")
    print()
    print(format_report(df))

    if args.csv and not df.empty:
        df.to_csv(args.csv, index=False)
        print(f"\nCSV exported: {args.csv} ({len(df)} rows)")


if __name__ == "__main__":
    main()
