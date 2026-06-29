#!/usr/bin/env python3
"""Falsification test: is Yegor's trade SELECTION a real edge, or hindsight?

For each of his 211 real trades, REPLAY the actual decision (entry, direction,
SL, TP) forward on real price data, causally, net of spread — ignoring the
recorded win/loss (which is hindsight-graded). Then compare to a NULL: random
entries on the SAME symbol with the SAME risk distance, RR and direction.

If his realized expectancy beats the random null (net of cost) on data the levels
were not fit to, the selection edge is real and extractable -> worth building on.
If his picks ~= random picks, the 83% WR is hindsight and there's nothing to encode.

This is the gate that decides whether a foundation exists at all.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backtesting.engine.data import load_data
from backtesting.scripts.forensics import load_trades

CAP = 500          # max bars to resolve a trade
N_NULL = 30        # random controls per trade
RNG = np.random.default_rng(42)


def spread_price(sym: str) -> float:
    """Rough round-trip spread in PRICE units (conservative retail/prop)."""
    if sym == "BTCUSD":          return 20.0      # ~$20
    if sym == "USATECHIDXUSD":   return 1.0       # ~1 index pt
    if "JPY" in sym:             return 0.01 * 1.5 # ~1.5 pip
    if sym.endswith("USD") or sym.startswith("USD"): return 0.0001 * 0.8
    return 0.0001 * 2.0          # crosses


def resolve(h, l, c, ei, entry, sl, tp, dirv, risk_px, cost_R):
    """Causal SL/TP/timecap resolution from bar ei. Returns realized R net cost."""
    n = len(c)
    cap = min(ei + CAP, n)
    for j in range(ei, cap):
        if dirv == 1:
            if l[j] <= sl:  return (sl - entry) / risk_px - cost_R   # SL first
            if h[j] >= tp:  return (tp - entry) / risk_px - cost_R
        else:
            if h[j] >= sl:  return (entry - sl) / risk_px - cost_R
            if l[j] <= tp:  return (entry - tp) / risk_px - cost_R
    jx = min(cap - 1, n - 1)
    return (c[jx] - entry) / risk_px * dirv - cost_R                 # time-cap


def main() -> None:
    trades = load_trades()
    cache: dict = {}
    his, nul, recs, next_fav = [], [], [], []
    for tr in trades:
        key = (tr["symbol"], tr["tf"])
        if key not in cache:
            try:
                df = load_data(tr["symbol"], tf=tr["tf"])
                cache[key] = df if not df.empty else None
            except Exception:
                cache[key] = None
        df = cache[key]
        if df is None:
            continue
        ts = (df["ts"].astype("int64") // 10**9).to_numpy()
        h = df["high"].to_numpy(float); l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
        n = len(c)
        i = int(np.argmin(np.abs(ts - tr["entry_time"])))
        if i < 50 or i >= n - 5:
            continue
        dirv = 1 if tr["direction"] == "long" else -1
        risk_px = abs(tr["entry"] - tr["sl"])
        atr = float(np.mean(h[i-30:i] - l[i-30:i])) or 1e-9
        if risk_px < 0.2 * atr:                # degenerate hindsight stop
            continue
        rr = abs(tr["tp"] - tr["entry"]) / risk_px
        cost_R = spread_price(tr["symbol"]) / risk_px
        # HIS actual trade
        hr = resolve(h, l, c, i, tr["entry"], tr["sl"], tr["tp"], dirv, risk_px, cost_R)
        his.append(hr)
        # hindsight tell: did price move his way on the VERY NEXT bar? (random ~50%)
        next_fav.append((c[i + 1] - tr["entry"]) * dirv > 0)
        # NULL: random entries, same symbol/dir/risk/rr
        ctrl = []
        lo, hi = 50, n - 5
        for _ in range(N_NULL):
            ri = int(RNG.integers(lo, hi))
            e = c[ri]
            if dirv == 1:
                sl = e - risk_px; tp = e + rr * risk_px
            else:
                sl = e + risk_px; tp = e - rr * risk_px
            ctrl.append(resolve(h, l, c, ri, e, sl, tp, dirv, risk_px, cost_R))
        nr = float(np.mean(ctrl))
        nul.append(nr)
        recs.append(dict(symbol=tr["symbol"], tf=tr["tf"], dir=tr["direction"],
                         rr=rr, his_R=hr, null_R=nr, edge=hr - nr,
                         trigger=tr.get("trigger", "?")))

    if not recs:
        print("no replayable trades (data missing)"); return
    d = pd.DataFrame(recs)
    his = np.array(his); nul = np.array(nul)

    def stats(x):
        return (x.mean(), (x > 0).mean() * 100,
                x[x > 0].mean() if (x > 0).any() else 0.0,
                x[x <= 0].mean() if (x <= 0).any() else 0.0)

    hm, hwr, haw, hal = stats(his)
    nm, nwr, naw, nal = stats(nul)
    edge = his - nul
    # paired t-ish: mean / SE
    se = edge.std(ddof=1) / np.sqrt(len(edge)) if len(edge) > 1 else np.nan
    tstat = edge.mean() / se if se and se > 0 else float("nan")

    print(f"replayable trades: {len(d)} / 211   symbols: {sorted(d.symbol.unique())}\n")
    print(f"{'':14}{'expR':>8}{'WR':>8}{'avgWin':>8}{'avgLoss':>9}")
    print(f"{'HIS picks':14}{hm:>+8.3f}{hwr:>7.1f}%{haw:>8.2f}{hal:>9.2f}")
    print(f"{'RANDOM null':14}{nm:>+8.3f}{nwr:>7.1f}%{naw:>8.2f}{nal:>9.2f}")
    print(f"\nSELECTION EDGE (his - null), per-trade paired:")
    print(f"  mean = {edge.mean():+.3f} R   SE = {se:.3f}   t = {tstat:.2f}   "
          f"pairs his>null = {(edge>0).mean()*100:.0f}%")

    # HINDSIGHT GUARD: if entries are favorable on the next bar far above chance,
    # the timing is look-ahead and the edge number is an artifact, NOT alpha.
    nf = np.array(next_fav)
    nf_pct = nf.mean() * 100
    hindsight = nf_pct > 60
    print(f"\nhindsight check: favorable on the very next bar = {nf_pct:.0f}% "
          f"(random ~50%; >60% = look-ahead-timed entries)")
    if hindsight:
        print("verdict: ⛔️ HINDSIGHT ARTIFACT — entries are look-ahead-timed; the edge "
              "number is NOT real. Need forward-committed (blinded) decisions to test selection.")
    elif tstat == tstat and tstat > 2 and hm > 0:
        print("verdict: ✅ REAL edge — selection beats random net of cost, no hindsight tell.")
    else:
        print("verdict: NOT proven — picks ≈ random.")
    print("\nby symbol (his expR vs null expR, net cost):")
    for s, g in d.groupby("symbol"):
        print(f"  {s:14} n={len(g):3}  his={g.his_R.mean():+.3f}  null={g.null_R.mean():+.3f}  edge={g.edge.mean():+.3f}")
    print("\nby trigger (his expR net cost):")
    for s, g in d.groupby("trigger"):
        if len(g) >= 8:
            print(f"  {s:16} n={len(g):3}  his={g.his_R.mean():+.3f}  edge={g.edge.mean():+.3f}")


if __name__ == "__main__":
    main()
