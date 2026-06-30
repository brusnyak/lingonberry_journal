#!/usr/bin/env python3
"""
Level 0 — Statistical Pocket Scan.

Scans all available (pair, timeframe, session, direction) pockets for
statistically significant forward return edge.

Usage:
    python -m hypothesis_engine.level0_statistical.run --help
    python -m hypothesis_engine.level0_statistical.run --quick
    python -m hypothesis_engine.level0_statistical.run --full --csv results.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

# Allow running from repo root
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hypothesis_engine.level0_statistical.scanner import (
    scan_pocket,
    scan_all_pairs,
    SESSIONS,
)
from hypothesis_engine.level0_statistical.report import (
    format_results,
    pocket_row,
    POCKET_HEADER,
    _count_significant,
)


# Quick scan: most active forex pairs + XAUUSD
QUICK_PAIRS = [
    "EURUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD",
    "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "AUDJPY",
    "NZDUSD", "EURJPY", "EURGBP", "EURAUD", "EURCHF",
    "XAUUSD", "USATECHIDXUSD",  # gold + NAS100
]

# Standard TFs
QUICK_TFS = ("5", "15", "60", "240")
FULL_TFS = ("1", "5", "15", "30", "60", "240")


def run_scan(
    pairs: list[str],
    tfs: tuple[str, ...],
    days: int = 60,
    allow_oos: bool = False,
    verbose: bool = True,
) -> list[dict]:
    """Run the statistical scan over all pairs and TFs."""
    results = []
    total = len(pairs) * len(tfs)
    done = 0

    print(f"Scanning {total} pair/TF combos ({days}d window)...")
    print()

    for sym in pairs:
        for tf in tfs:
            done += 1
            t0 = time.time()
            r = scan_pocket(sym, tf, days=days, allow_oos=allow_oos)
            elapsed = time.time() - t0

            if verbose:
                from hypothesis_engine.level0_statistical.report import pocket_summary
                print(f"  [{done:>3}/{total}] {pocket_summary(r)}  ({elapsed:.2f}s)")

            results.append(r)

    return results


def export_csv(results: list[dict], path: str) -> None:
    """Flatten results to CSV."""
    rows = []
    for r in results:
        if "error" in r:
            continue
        for sname, sdata in r.get("sessions", {}).items():
            for key, stats in sdata.items():
                direction, horizon = key.split("_")
                rows.append({
                    "symbol": r["symbol"],
                    "tf": r["tf"],
                    "session": sname,
                    "direction": direction,
                    "horizon": int(horizon),
                    "n": stats["n"],
                    "mean_ret": stats["mean_ret"],
                    "win_rate": stats["win_rate"],
                    "profit_factor": stats["profit_factor"],
                    "t_stat": stats["t_stat"],
                    "ci_low": stats["ci_low"],
                    "ci_high": stats["ci_high"],
                    "ci_contains_zero": stats["ci_contains_zero"],
                    "effect_size": stats["effect_size"],
                })

    with open(path, "w", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
    print(f"\nCSV exported: {path} ({len(rows)} rows)")


def main():
    parser = argparse.ArgumentParser(description="Level 0 — Statistical Pocket Scan")
    parser.add_argument("--quick", action="store_true", help="Scan active pairs only")
    parser.add_argument("--full", action="store_true", help="Scan ALL available forex pairs")
    parser.add_argument("--pairs", type=str, default="", help="Comma-separated override")
    parser.add_argument("--tfs", type=str, default="", help="Comma-separated TFs (e.g. '5,15,60')")
    parser.add_argument("--days", type=int, default=60, help="Data window in days")
    parser.add_argument("--oos", action="store_true", help="Include OOS data")
    parser.add_argument("--csv", type=str, default="", help="Export to CSV path")
    parser.add_argument("--min-pockets", type=int, default=0, help="Min pockets to show in report")
    args = parser.parse_args()

    # Determine pairs
    if args.pairs:
        pairs = [p.strip().upper() for p in args.pairs.split(",")]
    elif args.full:
        from backtesting.engine.data import list_pairs
        pairs = [p for p in list_pairs("forex") if p.isascii() and len(p) > 3 and not any(c.isdigit() for c in p)]
        pairs = sorted(set(pairs))[:30]
    else:
        pairs = QUICK_PAIRS

    # Determine TFs
    tfs = tuple(t.strip() for t in args.tfs.split(",")) if args.tfs else QUICK_TFS

    print(f"Level 0 — Statistical Foundation")
    print(f"Pairs: {len(pairs)}  TFs: {tfs}  Window: {args.days}d  OOS: {args.oos}")
    print()

    results = run_scan(pairs, tfs, days=args.days, allow_oos=args.oos)

    print()
    print(format_results(results, min_pockets=args.min_pockets))

    if args.csv:
        export_csv(results, args.csv)


if __name__ == "__main__":
    main()
