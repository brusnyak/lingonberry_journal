#!/usr/bin/env python3
"""
Key-level sweep+reclaim v0 vs random-direction null.

IS-only (OOS wall). The null fires on the SAME bars with the SAME risk distance
the real signal computed, but flips direction by coin-toss → identical frequency,
isolates whether the reclaim DIRECTION is an edge. Reject the strategy unless it
clears the null after costs.

    python -m backtesting.baselines.run_kl_sweep
    python -m backtesting.baselines.run_kl_sweep --reclaim ema20 --rr 1.0 \
        --pair GBPAUD --null-seeds 50
"""
from __future__ import annotations

import argparse
import random
from typing import Optional

import numpy as np

from backtesting.engine.costs import ForexCosts
from backtesting.engine.data import load_data
from backtesting.engine.orders import Direction, Signal
from backtesting.engine.runner import run
from backtesting.strategies.kl_sweep_reclaim_v0 import KlSweepReclaimV0
from backtesting.baselines.run_donchian import _print_report


class RandomDirNull(KlSweepReclaimV0):
    """Same trigger bars + same risk distance as the real strategy, random direction."""

    def __init__(self, *args, seed: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(seed)

    def next(self, bar, state) -> Optional[Signal]:
        sig = super().next(bar, state)
        if sig is None:
            return None
        entry = sig.entry
        sl_dist = abs(entry - sig.sl)
        tp_dist = abs(sig.tp1 - entry)
        if self._rng.random() < 0.5:
            return Signal(direction=Direction.LONG, entry=entry, sl=entry - sl_dist,
                          tp1=entry + tp_dist, risk_pct=self.risk_pct,
                          tp1_frac=1.0, trail=False, label="null_long")
        return Signal(direction=Direction.SHORT, entry=entry, sl=entry + sl_dist,
                      tp1=entry - tp_dist, risk_pct=self.risk_pct,
                      tp1_frac=1.0, trail=False, label="null_short")


def _losing_streak(report: dict) -> int:
    return int(report.get("max_consec_losses", 0))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="GBPAUD")
    ap.add_argument("--tf", default="15")
    ap.add_argument("--reclaim", default="vwap", choices=["vwap", "ema20"])
    ap.add_argument("--sweep-lookback", type=int, default=6)
    ap.add_argument("--atr-buffer", type=float, default=0.5)
    ap.add_argument("--rr", type=float, default=1.5)
    ap.add_argument("--risk", type=float, default=0.005)
    ap.add_argument("--equity", type=float, default=10_000.0)
    ap.add_argument("--no-regime", action="store_true")
    ap.add_argument("--null-seeds", type=int, default=50)
    args = ap.parse_args()

    df = load_data(args.pair, tf=args.tf, days=99999)  # IS-only
    if df.empty:
        print(f"No IS data for {args.pair} {args.tf}m")
        return
    data = {args.tf: df}
    total_minutes = (df["ts"].max() - df["ts"].min()).total_seconds() / 60
    print(f"{args.pair} {args.tf}m | IS {df['ts'].min().date()} -> {df['ts'].max().date()} "
          f"| {len(df):,} bars")
    print(f"KL sweep+reclaim v0: reclaim={args.reclaim} sweep_lb={args.sweep_lookback} "
          f"atr_buf={args.atr_buffer} rr={args.rr} regime={not args.no_regime} "
          f"risk={args.risk:.2%} | next-bar-open fill")

    kw = dict(reclaim=args.reclaim, sweep_lookback=args.sweep_lookback,
              atr_buffer=args.atr_buffer, rr=args.rr, risk_pct=args.risk,
              use_regime=not args.no_regime, entry_tf=args.tf)

    res = run(KlSweepReclaimV0(**kw), data, entry_tf=args.tf, costs=ForexCosts(seed=0),
              initial_equity=args.equity, next_bar_fill=True)
    _print_report("KL SWEEP+RECLAIM v0", res.report, total_minutes)
    print(f"  {'Max lose streak':<16} {_losing_streak(res.report)}")

    if not res.report.get("trades"):
        print("\nNo trades — nothing to compare. Loosen filters or check data.")
        return

    null_returns = []
    for s in range(args.null_seeds):
        nres = run(RandomDirNull(seed=s, **kw), data, entry_tf=args.tf,
                   costs=ForexCosts(seed=0), initial_equity=args.equity, next_bar_fill=True)
        null_returns.append(nres.report.get("return_pct", 0.0))
    nr = np.array(null_returns)
    don = res.report.get("return_pct", 0.0)
    pctile = float((nr < don).mean() * 100)

    print(f"\nRANDOM-DIRECTION NULL  (n={args.null_seeds} seeds, same bars + risk)")
    print("-" * 56)
    print(f"  Return mean      {nr.mean():+.2%}")
    print(f"  Return std       {nr.std():.2%}")
    print(f"  Return range     {nr.min():+.2%} .. {nr.max():+.2%}")

    print("\nVERDICT")
    print("-------")
    print(f"  Strategy return {don:+.2%} at the {pctile:.0f}th percentile of the null.")
    accept = pctile >= 95 and don > 0 and res.report.get("profit_factor", 0) > 1.0
    if accept:
        print("  -> ACCEPT for now: beats null, positive, PF>1. Next: rolling windows.")
    elif pctile >= 95:
        print("  -> Beats null on direction but not net-profitable after costs. "
              "Lever = frequency/RR, not direction.")
    else:
        print("  -> REJECT: inside the noise band. No edge after costs.")


if __name__ == "__main__":
    main()
