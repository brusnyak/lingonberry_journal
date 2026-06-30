#!/usr/bin/env python3
"""
Baseline run: Donchian breakout v0 vs a random-direction null.

IS-ONLY by construction (load_data defaults to the OOS wall). The null shares
Donchian's exact entry TIMING but flips direction by coin-toss, so any edge
over the null is edge in the breakout *direction*, not in trade count or
market drift. If Donchian's return sits inside the null's spread, it's noise.

    python -m backtesting.baselines.run_donchian
    python -m backtesting.baselines.run_donchian --pair GBPAUD --tf 15 \
        --lookback 20 --atr-mult 1.5 --rr 1.5 --null-seeds 50
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
from backtesting.strategies.donchian_v0 import DonchianV0


class RandomDirNull(DonchianV0):
    """Fires on the SAME bars as DonchianV0, but direction is a coin-flip."""

    def __init__(self, *args, seed: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self._rng = random.Random(seed)

    def next(self, bar, state) -> Optional[Signal]:
        sig = super().next(bar, state)
        if sig is None:
            return None
        # Re-cast direction randomly, recompute SL/TP around the same entry.
        close = sig.entry
        sl_dist = self.atr_mult * self.atr[bar.index]
        tp_dist = self.rr * sl_dist
        if self._rng.random() < 0.5:
            return Signal(direction=Direction.LONG, entry=close, sl=close - sl_dist,
                          tp1=close + tp_dist, risk_pct=self.risk_pct,
                          tp1_frac=1.0, trail=False, label="null_long")
        return Signal(direction=Direction.SHORT, entry=close, sl=close + sl_dist,
                      tp1=close - tp_dist, risk_pct=self.risk_pct,
                      tp1_frac=1.0, trail=False, label="null_short")


METRIC_KEYS = [
    ("return_pct", "Total return", "{:+.2%}"),
    ("max_drawdown_pct", "Max drawdown", "{:.2%}"),
    ("win_rate", "Win rate", "{:.1%}"),
    ("avg_r", "Avg R", "{:+.3f}"),
    ("profit_factor", "Profit factor", "{:.2f}"),
    ("trades", "Trades", "{:.0f}"),
    ("expectancy", "Expectancy ($)", "{:+.2f}"),
    ("sharpe", "Sharpe (daily)", "{:.2f}"),
]


def _print_report(title: str, rep: dict, total_minutes: float = 0.0) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    for key, label, fmt in METRIC_KEYS:
        if key in rep:
            try:
                print(f"  {label:<16} {fmt.format(rep[key])}")
            except (ValueError, TypeError):
                print(f"  {label:<16} {rep[key]}")
    # Exposure ≈ time in market / total span
    if total_minutes > 0 and rep.get("trades"):
        in_market = rep.get("avg_duration_min", 0.0) * rep["trades"]
        print(f"  {'Exposure':<16} {in_market/total_minutes:.1%}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="GBPAUD")
    ap.add_argument("--tf", default="15")
    ap.add_argument("--lookback", type=int, default=20)
    ap.add_argument("--atr-mult", type=float, default=1.5)
    ap.add_argument("--rr", type=float, default=1.5)
    ap.add_argument("--risk", type=float, default=0.005)
    ap.add_argument("--equity", type=float, default=10_000.0)
    ap.add_argument("--null-seeds", type=int, default=50)
    args = ap.parse_args()

    df = load_data(args.pair, tf=args.tf, days=99999)  # IS-only via OOS wall
    if df.empty:
        print(f"No IS data for {args.pair} {args.tf}m")
        return
    data = {args.tf: df}
    print(f"{args.pair} {args.tf}m | IS {df['ts'].min().date()} -> {df['ts'].max().date()} "
          f"| {len(df):,} bars")
    print(f"Donchian v0: lookback={args.lookback} atr_mult={args.atr_mult} "
          f"rr={args.rr} risk={args.risk:.2%} | next-bar-open fill")

    def make_costs():
        return ForexCosts(seed=0)

    # ── Donchian ──
    strat = DonchianV0(lookback=args.lookback, atr_mult=args.atr_mult, rr=args.rr,
                       risk_pct=args.risk, entry_tf=args.tf)
    res = run(strat, data, entry_tf=args.tf, costs=make_costs(),
              initial_equity=args.equity, next_bar_fill=True)
    total_minutes = (df["ts"].max() - df["ts"].min()).total_seconds() / 60
    _print_report("DONCHIAN v0", res.report, total_minutes)

    # ── Random-direction null distribution ──
    null_returns, null_pfs = [], []
    for s in range(args.null_seeds):
        nstrat = RandomDirNull(lookback=args.lookback, atr_mult=args.atr_mult,
                               rr=args.rr, risk_pct=args.risk, entry_tf=args.tf, seed=s)
        nres = run(nstrat, data, entry_tf=args.tf, costs=ForexCosts(seed=0),
                   initial_equity=args.equity, next_bar_fill=True)
        null_returns.append(nres.report.get("return_pct", 0.0))
        pf = nres.report.get("profit_factor", 0.0)
        if np.isfinite(pf):
            null_pfs.append(pf)

    nr = np.array(null_returns)
    don_ret = res.report.get("return_pct", 0.0)
    pctile = float((nr < don_ret).mean() * 100)
    print(f"\nRANDOM-DIRECTION NULL  (n={args.null_seeds} seeds, same entry timing)")
    print("-" * 54)
    print(f"  Return mean      {nr.mean():+.2%}")
    print(f"  Return std       {nr.std():.2%}")
    print(f"  Return range     {nr.min():+.2%} .. {nr.max():+.2%}")
    print(f"  Mean PF          {np.mean(null_pfs):.2f}" if null_pfs else "  Mean PF          n/a")

    print("\nVERDICT")
    print("-------")
    print(f"  Donchian return {don_ret:+.2%} sits at the {pctile:.0f}th percentile of the null.")
    if pctile >= 95:
        print("  -> Beats the monkey decisively. Worth a rolling-window test.")
    elif pctile >= 80:
        print("  -> Edge over chance, not yet convincing. Rolling test before trusting.")
    else:
        print("  -> Inside the noise band. The breakout direction is NOT an edge here.")


if __name__ == "__main__":
    main()
