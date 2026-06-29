"""Lvl 0 (the REAL foundation) — feasibility envelope for the prop goal.

Before building any signal, answer: given a per-trade edge (win rate W, payoff
b = reward:risk) and a frequency (F trades per 30-day window) at risk-per-trade
r, what is P(PASS) = P(reach +TARGET before max drawdown breaches DD_LIMIT)?

This is a PATH problem (DD is path-dependent), simulated trade-by-trade with the
real prop stopping rules: a window PASSES the instant cumulative return hits the
target while drawdown has never breached the cap; it FAILS if the cap is breached
first or the window ends short. Output tells us the MINIMUM edge + frequency the
8%/<3%DD target actually requires — so we never build a signal that can't clear
the bar even if its edge is real.
"""
from __future__ import annotations

import numpy as np

TARGET = 0.08      # +8% return goal
DD_LIMIT = 0.03    # <3% max drawdown from peak (Yegor's conservative cap)
M = 40_000         # sims per cell


def p_pass(W: float, b: float, F: int, r: float,
           target: float = TARGET, dd_limit: float = DD_LIMIT, m: int = M) -> float:
    rng = np.random.default_rng(0)
    eq = np.ones(m)
    peak = np.ones(m)
    done = np.zeros(m, bool)     # path resolved (passed or failed)
    passed = np.zeros(m, bool)
    for _ in range(F):
        win = rng.random(m) < W
        step = np.where(win, b * r, -r)
        live = ~done
        eq[live] *= (1 + step[live])
        peak = np.maximum(peak, eq)
        dd = (peak - eq) / peak
        # fail first (conservative: DD checked same step)
        failed = live & (dd > dd_limit)
        done |= failed
        live = ~done
        win_now = live & ((eq - 1) >= target)
        passed |= win_now
        done |= win_now
    return passed.mean()


def expectancy_R(W: float, b: float) -> float:
    return W * b - (1 - W)  # per-trade EV in R units


def main() -> None:
    Ws = [0.45, 0.50, 0.55]
    bs = [1.0, 1.5, 2.0, 3.0]
    Fs = [5, 10, 20, 40]
    rs = [0.0025, 0.005, 0.01]  # 0.25%, 0.5%, 1% risk/trade

    print(f"Goal: +{TARGET:.0%} before -{DD_LIMIT:.0%} maxDD, within one 30-day window\n")
    for W in Ws:
        for b in bs:
            e = expectancy_R(W, b)
            tag = "  (NEG EV)" if e <= 0 else ""
            print(f"--- W={W:.0%}  b={b:.1f}R  edge={e:+.2f}R/trade{tag} ---")
            header = "  r\\F  " + "".join(f"{F:>8d}" for F in Fs)
            print(header)
            for r in rs:
                cells = "".join(f"{p_pass(W,b,F,r):>8.2f}" for F in Fs)
                print(f"  {r:.3%}" + cells)
            print()


if __name__ == "__main__":
    main()
