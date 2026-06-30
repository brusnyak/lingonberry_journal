#!/usr/bin/env python3
"""
Rolling window pocket validation — Level 0 extension.

Loads all available data for each pair/TF, slides a 30-day window
with 15-day stride, and checks which pockets are CONSISTENTLY
significant across time.

Usage:
    python -m hypothesis_engine.level0_statistical.run_rolling --quick
    python -m hypothesis_engine.level0_statistical.run_rolling --full
    python -m hypothesis_engine.level0_statistical.run_rolling --csv results.csv
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hypothesis_engine.level0_statistical.scanner import run_rolling_all


QUICK_PAIRS = [
    "EURUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD",
    "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "AUDJPY",
    "NZDUSD", "EURJPY", "EURGBP", "EURAUD", "EURCHF",
    "XAUUSD", "USATECHIDXUSD",
]
QUICK_TFS = ("5", "15", "60", "240")


def format_rolling_report(df) -> str:
    """Format aggregated rolling results as a readable table."""
    if df.empty:
        return "No results."

    lines = []
    lines.append("=" * 130)
    lines.append("ROLLING WINDOW VALIDATION — Top Consistent Pockets")
    lines.append("=" * 130)
    header = (
        f"{'Symbol':<10} {'TF':>3} {'Session':<10} {'Dir':<5} {'H':>2} "
        f"{'Wins':>4} {'Sig':>4} {'Stab':>5} {'MeanRet':>9} {'t_avg':>7} "
        f"{'PF_avg':>6} {'WR_avg':>6} {'Score':>6}"
    )
    lines.append(header)
    lines.append("-" * 130)

    # Show top 40 pockets ranked by score
    for _, row in df.head(40).iterrows():
        sig_pct = f"{row['n_significant']}/{row['n_windows']}"
        stab = f"{row['stability']:.0%}"
        lines.append(
            f"{row['symbol']:<10} {str(row['tf']):>3} {row['session']:<10} "
            f"{row['direction']:<5} {int(row['horizon']):>2} "
            f"{int(row['n_windows']):>4} {sig_pct:>7} {stab:>5} "
            f"{row['mean_mean_ret']:>+9.6f} {row['avg_t_stat']:>+7.2f} "
            f"{row['avg_pf']:>6.2f} {row['avg_wr']:>6.1%} "
            f"{row['score']:>6.2f}"
        )

    lines.append("-" * 130)
    lines.append(f"Total pockets tracked: {len(df)}")
    lines.append(f"  Consistent (stability=100%): {(df['consistent']).sum()}")
    lines.append(f"  Significant in all windows: {((df['n_significant'] == df['n_windows'])).sum()}")
    lines.append("=" * 130)

    # Separate by sign
    positive = df[df['sign'] > 0].head(15)
    negative = df[df['sign'] < 0].head(15)

    if not positive.empty:
        lines.append("")
        lines.append("TOP POSITIVE (momentum) pockets:")
        lines.append(f"{'Symbol':<10} {'TF':>3} {'Session':<10} {'Dir':<5} {'H':>2} "
                     f"{'MeanRet':>9} {'t_avg':>7} {'WR':>6} {'Stab':>5}")
        for _, row in positive.iterrows():
            lines.append(
                f"{row['symbol']:<10} {str(row['tf']):>3} {row['session']:<10} "
                f"{row['direction']:<5} {int(row['horizon']):>2} "
                f"{row['mean_mean_ret']:>+9.6f} {row['avg_t_stat']:>+7.2f} "
                f"{row['avg_wr']:>6.1%} {row['stability']:.0%}"
            )

    if not negative.empty:
        lines.append("")
        lines.append("TOP NEGATIVE (mean-reversion) pockets:")
        lines.append(f"{'Symbol':<10} {'TF':>3} {'Session':<10} {'Dir':<5} {'H':>2} "
                     f"{'MeanRet':>9} {'t_avg':>7} {'WR':>6} {'Stab':>5}")
        for _, row in negative.iterrows():
            lines.append(
                f"{row['symbol']:<10} {str(row['tf']):>3} {row['session']:<10} "
                f"{row['direction']:<5} {int(row['horizon']):>2} "
                f"{row['mean_mean_ret']:>+9.6f} {row['avg_t_stat']:>+7.2f} "
                f"{row['avg_wr']:>6.1%} {row['stability']:.0%}"
            )

    lines.append("")
    lines.append("=" * 130)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Rolling Window Pocket Validation")
    parser.add_argument("--quick", action="store_true", help="Quick scan (17 pairs, 4 TFs)")
    parser.add_argument("--full", action="store_true", help="All forex pairs")
    parser.add_argument("--pairs", type=str, default="", help="Comma-separated override")
    parser.add_argument("--tfs", type=str, default="", help="Comma-separated TFs")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=15)
    parser.add_argument("--csv", type=str, default="", help="Export to CSV")
    parser.add_argument("--no-oos", action="store_true", help="Exclude OOS data (default: include)")
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

    print(f"Rolling Window Validation")
    print(f"  Pairs: {len(pairs)}  TFs: {tfs}")
    print(f"  Window: {args.window_days}d  Step: {args.step_days}d")
    print(f"  OOS: {'excluded' if args.no_oos else 'included'}")
    print()

    t0 = time.time()
    df = run_rolling_all(
        symbols=pairs,
        tfs=tfs,
        window_days=args.window_days,
        step_days=args.step_days,
        allow_oos=not args.no_oos,
        verbose=True,
    )
    elapsed = time.time() - t0

    print()
    print(f"Completed in {elapsed:.1f}s")
    print()
    print(format_rolling_report(df))

    if args.csv and not df.empty:
        df.to_csv(args.csv, index=False)
        print(f"\nCSV exported: {args.csv} ({len(df)} rows)")


if __name__ == "__main__":
    main()
