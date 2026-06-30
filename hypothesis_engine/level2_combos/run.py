#!/usr/bin/env python3
"""
Level 2 — Condition combination scanner.

Tests pairs of conditions stacked with AND logic (both must agree).
"""
from __future__ import annotations

import argparse, sys, time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hypothesis_engine.level2_combos.scanner import run_all, COMBO_PAIRS

QUICK_PAIRS = [
    "EURUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD",
    "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "AUDJPY",
    "NZDUSD", "EURJPY", "EURGBP", "EURAUD", "EURCHF",
    "XAUUSD", "USATECHIDXUSD",
]
QUICK_TFS = ("5", "15", "60", "240")


def format_report(df) -> str:
    if df.empty:
        return "No results."
    lines = []
    lines.append("=" * 140)
    lines.append("LEVEL 2 — CONDITION COMBINATION SCAN")
    lines.append("=" * 140)
    hdr = (f"{'Symbol':<10} {'TF':>3} {'Combo':<15} {'Signal':<6} {'Session':<10} "
           f"{'H':>2} {'Sig/All':>7} {'Stab':>5} {'MeanRet':>9} {'t_avg':>7} "
           f"{'WR':>6} {'PF':>6} {'Score':>5}")
    lines.append(hdr)
    lines.append("-" * 140)
    for _, r in df.head(40).iterrows():
        sig = f"{int(r['n_significant'])}/{int(r['n_windows'])}"
        lines.append(
            f"{r['symbol']:<10} {str(r['tf']):>3} {r['combo']:<15} {r['signal_dir']:<6} "
            f"{r['session']:<10} {int(r['horizon']):>2} {sig:>7} "
            f"{r['stability']:.0%} {r['mean_mean_ret']:>+9.6f} {r['avg_t_stat']:>+7.2f} "
            f"{r['avg_wr']:>6.1%} {r['avg_pf']:>6.2f} {r['score']:>5.2f}")
    lines.append("-" * 140)
    lines.append(f"Total combo-pockets: {len(df)}")
    lines.append(f"  Consistent (100%): {(df['consistent']).sum()}")
    lines.append(f"  |t|>2 & stab>80%: {len(df[(df['avg_t_stat'].abs()>2)&(df['stability']>0.80)])}")
    lines.append("=" * 140)

    lines.append("")
    lines.append("BEST PER COMBO:")
    for c in df['combo'].unique():
        best = df[df['combo'] == c].head(3)
        if best.empty:
            continue
        lines.append(f"  {c}:")
        for _, r in best.iterrows():
            lines.append(
                f"    {r['symbol']:<10} {str(r['tf']):>3}m {r['signal_dir']:<6} "
                f"{r['session']:<10} h={int(r['horizon']):>2} "
                f"mean={r['mean_mean_ret']:>+9.6f} t={r['avg_t_stat']:>+6.2f} "
                f"stab={r['stability']:.0%} wr={r['avg_wr']:>5.1%} pf={r['avg_pf']:>6.2f}")
    lines.append("")
    lines.append("=" * 140)
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Level 2 — Condition Combo Scanner")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--pairs", type=str, default="")
    p.add_argument("--tfs", type=str, default="")
    p.add_argument("--combo", type=str, default="", help="e.g. 'bos+fvg'")
    p.add_argument("--csv", type=str, default="")
    p.add_argument("--no-oos", action="store_true")
    args = p.parse_args()

    pairs = [s.strip().upper() for s in args.pairs.split(",")] if args.pairs else QUICK_PAIRS
    tfs = tuple(t.strip() for t in args.tfs.split(",")) if args.tfs else QUICK_TFS
    combos = [tuple(c.strip().split("+")) for c in args.combo.split(",")] if args.combo else COMBO_PAIRS

    print(f"Level 2 — Condition Combination Scan")
    print(f"  Pairs: {len(pairs)}  TFs: {tfs}  Combos: {combos}")
    print(f"  Total runs: {len(pairs)*len(tfs)*len(combos)}")
    print()

    t0 = time.time()
    df = run_all(symbols=pairs, tfs=tfs, combos=combos, allow_oos=not args.no_oos, verbose=True)
    elapsed = time.time() - t0
    print(f"\nCompleted in {elapsed:.1f}s\n")
    print(format_report(df))
    if args.csv and not df.empty:
        df.to_csv(args.csv, index=False)
        print(f"\nCSV: {args.csv} ({len(df)} rows)")

if __name__ == "__main__":
    main()
