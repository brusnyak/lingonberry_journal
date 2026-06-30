#!/usr/bin/env python3
"""
Mean-reversion RSI+BB+ADX vs random-direction null. Our engine, IS-only.

Same discipline as the prior tests: seeded costs, next-bar-open fill, OOS wall,
random-direction null on the SAME entry bars + same risk distance (isolates
whether the FADE direction is an edge). Reject unless it beats null AND is
net-profitable after costs.

    python -m backtesting.baselines.run_mean_rev
    python -m backtesting.baselines.run_mean_rev --pairs GBPAUD,EURGBP,GBPCAD,GBPCHF,AUDCAD
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
from backtesting.strategies.mean_rev_rsi_bb import MeanRevRsiBb
from backtesting.baselines.run_donchian import _print_report

INIT_EQ = 10_000.0


class RandomDirNull(MeanRevRsiBb):
    """Same trigger bars + same risk distance, random direction. Keeps the
    mean-revert exit (should_close branches on the position's own direction)."""

    def __init__(self, *args, seed: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(seed)

    def next(self, bar, state) -> Optional[Signal]:
        sig = super().next(bar, state)
        if sig is None:
            return None
        entry, sl_dist = sig.entry, abs(sig.entry - sig.sl)
        tp_dist = abs(sig.tp1 - sig.entry)
        if self._rng.random() < 0.5:
            return Signal(direction=Direction.LONG, entry=entry, sl=entry - sl_dist,
                          tp1=entry + tp_dist, risk_pct=self.risk_pct,
                          tp1_frac=1.0, trail=False, label="null_long")
        return Signal(direction=Direction.SHORT, entry=entry, sl=entry + sl_dist,
                      tp1=entry - tp_dist, risk_pct=self.risk_pct,
                      tp1_frac=1.0, trail=False, label="null_short")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="GBPAUD,EURGBP,GBPCAD,GBPCHF,AUDCAD")
    ap.add_argument("--tf", default="15")
    ap.add_argument("--risk", type=float, default=0.005)
    ap.add_argument("--adx", type=float, default=25.0)
    ap.add_argument("--atr-mult", type=float, default=1.5)
    ap.add_argument("--null-seeds", type=int, default=50)
    args = ap.parse_args()

    kw = dict(adx_threshold=args.adx, atr_mult=args.atr_mult, risk_pct=args.risk, entry_tf=args.tf)

    for pair in args.pairs.split(","):
        df = load_data(pair, tf=args.tf, days=99999)
        if df.empty:
            print(f"\n{pair}: no IS data"); continue
        data = {args.tf: df}
        total_minutes = (df["ts"].max() - df["ts"].min()).total_seconds() / 60

        res = run(MeanRevRsiBb(**kw), data, entry_tf=args.tf, costs=ForexCosts(seed=0),
                  initial_equity=INIT_EQ, next_bar_fill=True)
        print("\n" + "=" * 60)
        print(f"{pair} {args.tf}m | IS {df['ts'].min().date()} -> {df['ts'].max().date()} "
              f"| risk {args.risk:.2%} adx<{args.adx:.0f}")
        _print_report("MEAN-REV RSI+BB", res.report, total_minutes)
        print(f"  {'Max lose streak':<16} {int(res.report.get('max_consec_losses', 0))}")

        if not res.report.get("trades"):
            print("  (no trades)"); continue

        nr = []
        for s in range(args.null_seeds):
            nres = run(RandomDirNull(seed=s, **kw), data, entry_tf=args.tf,
                       costs=ForexCosts(seed=0), initial_equity=INIT_EQ, next_bar_fill=True)
            nr.append(nres.report.get("return_pct", 0.0))
        nr = np.array(nr)
        ret = res.report.get("return_pct", 0.0)
        pctile = float((nr < ret).mean() * 100)
        pf = res.report.get("profit_factor", 0.0)
        print(f"  null return mean {nr.mean():+.2%} (std {nr.std():.2%}) | "
              f"strat at {pctile:.0f}th pctile")
        verdict = ("ACCEPT (beats null + net-profitable)" if pctile >= 95 and ret > 0 and pf > 1.0
                   else "beats null, NOT net-profitable" if pctile >= 95
                   else "REJECT (inside noise)")
        print(f"  -> {verdict}")


if __name__ == "__main__":
    main()
