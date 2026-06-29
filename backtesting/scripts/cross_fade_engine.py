#!/usr/bin/env python3
"""Cross-fade engine: the build the data actually supports.

Universe = the 6 pairs whose fade/reversal bias survived the two-half period gate
(GBPAUD, EURAUD, AUDCHF, GBPCHF, AUDUSD, EURGBP). Thesis: these RANGE, so a
structure-continuation event (BOS/HH-in-bull / LL-in-bear) marks exhaustion ->
fade it. Edge lives in management, not the entry direction.

Rules (all causal):
  signal : continuation event at a swing/BOS, gated to non-trend regime -> FADE
  entry  : next bar open after the event bar
  SL     : structural invalidation (recent opposing swing) with an ATR floor
           (prior finding: tight structural stops get wicked + spread-eaten)
  TP     : fixed RR target; move SL->BE once +1R reached (let it breathe, protect)
  exit   : SL/TP forward-resolved bar-by-bar (SL assumed first if both in a bar);
           time cap. Spread cost applied per pair.

Output: per-interval 30d-window stats (median ret, median/worst DD, WR, avg RR,
%positive) for a small RR/floor sweep -> honest frontier, no curve-fitting.
Vectorized structure; per-trade resolution loop. Fast on the M1.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from backtesting.engine.data import load_data
from backtesting.features.structure import build_structure_index, StructureConfig
from backtesting.scripts.fade_edge_validate import continuation_dir

PAIRS = ["GBPAUD", "EURAUD", "AUDCHF", "GBPCHF", "AUDUSD", "EURGBP"]
INTERVALS = ["60", "15", "5"]
# rough round-trip spread in price (from meta_capture asset table)
SPREAD = {"GBPAUD": 0.00035, "EURAUD": 0.00032, "AUDCHF": 0.00028,
          "GBPCHF": 0.00035, "AUDUSD": 0.00016, "EURGBP": 0.00018}
RISK = 0.005          # 0.5% per trade
TIME_CAP = 96         # bars to force-exit


def trades_for(symbol: str, tf: str, days: int, rr: float, atr_floor: float,
               range_only: bool) -> pd.DataFrame:
    df = load_data(symbol, tf, days=days + 7, asset_type="forex")
    if df.empty or len(df) < 500:
        return pd.DataFrame()
    st = build_structure_index(df, StructureConfig(left=2, right=2))
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    ts = df["ts"].to_numpy()
    n = len(c)
    cont = continuation_dir(st)
    reg = st["regime"].to_numpy(dtype=object)
    sw_hi = st["last_swing_high"].to_numpy(float)
    sw_lo = st["last_swing_low"].to_numpy(float)
    # causal ATR(14)
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                      np.abs(l - np.r_[c[0], c[:-1]])))
    atr = pd.Series(tr).ewm(alpha=1/14, adjust=False).mean().to_numpy()
    sp = SPREAD[symbol]

    rows = []
    for i in range(2, n - 1):
        d = cont[i]
        if d == 0:
            continue
        if range_only and reg[i] == ("bull" if d == 1 else "bear"):
            continue  # skip when event aligns with a confirmed trend (let it run)
        fdir = -d                       # fade
        ei = i + 1                      # next-bar open entry
        entry = o[ei]
        a = atr[i] if np.isfinite(atr[i]) and atr[i] > 0 else (h[i] - l[i])
        floor = atr_floor * a
        if fdir == 1:  # fade long: structural SL below recent swing low
            struct = entry - sw_lo[i] if np.isfinite(sw_lo[i]) and sw_lo[i] < entry else floor
            risk_px = max(struct, floor)
            sl = entry - risk_px; tp = entry + rr * risk_px
        else:          # fade short: SL above recent swing high
            struct = sw_hi[i] - entry if np.isfinite(sw_hi[i]) and sw_hi[i] > entry else floor
            risk_px = max(struct, floor)
            sl = entry + risk_px; tp = entry - rr * risk_px
        if risk_px <= 0:
            continue
        cost_R = sp / risk_px
        be_armed = False; sl_cur = sl; realized = None
        cap = min(ei + TIME_CAP, n)
        for j in range(ei, cap):
            if fdir == 1:
                if l[j] <= sl_cur:      # SL first (conservative)
                    realized = (sl_cur - entry) / risk_px; break
                if h[j] >= tp:
                    realized = rr; break
                if not be_armed and h[j] >= entry + risk_px:
                    be_armed = True; sl_cur = entry
            else:
                if h[j] >= sl_cur:
                    realized = (entry - sl_cur) / risk_px; break
                if l[j] <= tp:
                    realized = rr; break
                if not be_armed and l[j] <= entry - risk_px:
                    be_armed = True; sl_cur = entry
        if realized is None:            # time-cap exit at close
            jx = min(cap - 1, n - 1)
            realized = (c[jx] - entry) / risk_px * fdir
        realized -= cost_R              # spread
        rows.append(dict(symbol=symbol, entry_ts=ts[ei], R=realized, rr=rr))
    return pd.DataFrame(rows)


def window_stats(trades: pd.DataFrame) -> pd.DataFrame:
    """Per 30d window: return, maxDD, WR, avgRR, n (0.5% risk, entry-ordered)."""
    if trades.empty:
        return pd.DataFrame()
    t = trades.sort_values("entry_ts").reset_index(drop=True)
    t["entry_ts"] = pd.to_datetime(t["entry_ts"])
    start = t["entry_ts"].min(); end = t["entry_ts"].max()
    rows = []
    w0 = start
    while w0 < end:
        w1 = w0 + pd.Timedelta(days=30)
        sub = t[(t.entry_ts >= w0) & (t.entry_ts < w1)]
        if len(sub) >= 5:
            eq = 1.0; peak = 1.0; mdd = 0.0
            for R in sub["R"].to_numpy():
                eq *= (1 + RISK * R)
                peak = max(peak, eq)
                mdd = max(mdd, (peak - eq) / peak)
            wins = (sub["R"] > 0).mean()
            avg_win = sub.loc[sub.R > 0, "R"].mean()
            avg_loss = sub.loc[sub.R <= 0, "R"].mean()
            rows.append(dict(window=w0.date(), n=len(sub), ret_pct=(eq - 1) * 100,
                             maxdd_pct=mdd * 100, wr=wins * 100,
                             avg_win_R=avg_win, avg_loss_R=avg_loss))
        w0 = w1
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=450)
    ap.add_argument("--intervals", default=",".join(INTERVALS))
    args = ap.parse_args()
    intervals = [s.strip() for s in args.intervals.split(",") if s.strip()]

    sweep = [(rr, fl, ro) for rr in (1.0, 1.5, 2.0) for fl in (0.8,) for ro in (True, False)]
    print(f"universe={PAIRS}\nrisk={RISK*100}%/trade  time_cap={TIME_CAP}  spread on\n")

    for tf in intervals:
        print(f"\n{'#'*72}\n# INTERVAL {tf}m\n{'#'*72}")
        for rr, fl, ro in sweep:
            allt = []
            for p in PAIRS:
                allt.append(trades_for(p, tf, args.days, rr, fl, ro))
            allt = [x for x in allt if not x.empty]
            if not allt:
                continue
            trades = pd.concat(allt, ignore_index=True)
            ws = window_stats(trades)
            if ws.empty:
                continue
            pos = (ws.ret_pct > 0).mean() * 100
            tag = f"RR={rr} floor={fl}ATR range_only={ro}"
            print(f"\n  [{tag}]  trades={len(trades)}  windows={len(ws)}")
            print(f"    median ret={ws.ret_pct.median():+.2f}%  median DD={ws.maxdd_pct.median():.2f}%  "
                  f"worst DD={ws.maxdd_pct.max():.2f}%")
            print(f"    WR={ws.wr.mean():.1f}%  avgWin={trades.loc[trades.R>0,'R'].mean():.2f}R  "
                  f"avgLoss={trades.loc[trades.R<=0,'R'].mean():.2f}R  windows +={pos:.0f}%")


if __name__ == "__main__":
    main()
