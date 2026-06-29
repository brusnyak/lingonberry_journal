#!/usr/bin/env python3
"""Validate the FADE/REVERSAL edge found in causal direction analysis.

Causal finding: structure-CONTINUATION signals (BOS_up, HH-in-bull, BOS_down,
LH-in-bear) run ~44-48% hit rate i.e. anti-predictive after costs. This tests
the INVERSE (fade the signal) honestly, per-pair, so we can see whether the edge
is consistent or concentrated in a few pairs/regimes (the yen-regime trap).

This is a DIRECTION study (time-exit forward return), not a tradeable backtest:
no SL/TP/management. It only answers "is the directional thesis right, net of a
rough spread cost?" Fully vectorized (no per-bar iloc) — fast on the M1.

Event -> continuation dir -> FADE dir:
  BOS_up        -> +1 -> fade SHORT
  BOS_down      -> -1 -> fade LONG
  HH in bull    -> +1 -> fade SHORT   (local top in uptrend)
  LH in bear    -> -1 -> fade LONG    (local top in downtrend... = continuation down; fade=long)
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

PAIRS = ["EURUSD","GBPUSD","AUDUSD","USDCAD","USDCHF","EURGBP","EURCHF","AUDNZD",
         "AUDCAD","AUDCHF","CADCHF","EURAUD","EURCAD","GBPAUD","GBPCAD","GBPCHF",
         "USDJPY","EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY"]
HORIZONS = [12, 24]
COST_BPS = 1.5  # rough round-trip spread; reported net AND gross


def continuation_dir(st: pd.DataFrame) -> np.ndarray:
    """+1/-1 continuation direction per bar at an event, else 0 (vectorized)."""
    n = len(st)
    d = np.zeros(n, dtype=np.int8)
    bos_up = st["bos_up"].to_numpy(dtype=bool)
    bos_dn = st["bos_down"].to_numpy(dtype=bool)
    lbl = st["structure_label"].to_numpy(dtype=object)
    reg = st["regime"].to_numpy(dtype=object)
    hh_bull = (lbl == "HH") & (reg == "bull")
    lh_bear = (lbl == "LH") & (reg == "bear")
    d[bos_up] = 1
    d[bos_dn] = -1
    d[hh_bull] = 1
    d[lh_bear] = -1
    return d


def analyze(symbol: str, days: int, left: int, right: int) -> list[dict]:
    atype = "commodity" if symbol == "XAUUSD" else "forex"
    df = load_data(symbol, "60", days=days + 7, asset_type=atype)
    if df.empty or len(df) < 300:
        return []
    st = build_structure_index(df, StructureConfig(left=left, right=right))
    close = df["close"].to_numpy(dtype=float)
    n = len(close)
    cont = continuation_dir(st)
    out = []
    for h in HORIZONS:
        fwd = np.full(n, np.nan)
        fwd[:n - h] = (close[h:] - close[:n - h]) / close[:n - h]
        ev = (cont != 0) & np.isfinite(fwd)
        if ev.sum() == 0:
            continue
        fade_dir = -cont[ev]               # fade = opposite of continuation
        r = fwd[ev]
        fade_ret_bps = fade_dir * r * 10_000   # signed return taking the fade side
        cont_ret_bps = cont[ev] * r * 10_000   # what continuation would have made
        out.append(dict(
            symbol=symbol, horizon=h, n=int(ev.sum()),
            fade_winrate=float((fade_ret_bps > 0).mean() * 100),
            fade_gross_bps=float(fade_ret_bps.mean()),
            fade_net_bps=float(fade_ret_bps.mean() - COST_BPS),
            cont_gross_bps=float(cont_ret_bps.mean()),
        ))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--left", type=int, default=2)
    ap.add_argument("--right", type=int, default=2)
    ap.add_argument("--pairs", default=",".join(PAIRS))
    args = ap.parse_args()
    pairs = [p.strip().upper() for p in args.pairs.split(",") if p.strip()]

    rows = []
    for p in pairs:
        rows.extend(analyze(p, args.days, args.left, args.right))
    if not rows:
        raise SystemExit("no events")
    d = pd.DataFrame(rows)

    for h in HORIZONS:
        sub = d[d.horizon == h].sort_values("fade_net_bps", ascending=False)
        if sub.empty:
            continue
        N = int(sub.n.sum())
        wr = float((sub.fade_winrate * sub.n).sum() / N)
        net = float((sub.fade_net_bps * sub.n).sum() / N)
        gross = float((sub.fade_gross_bps * sub.n).sum() / N)
        pos_pairs = int((sub.fade_net_bps > 0).sum())
        print(f"\n{'='*64}\n  FADE EDGE @ h={h} bars  (cost={COST_BPS}bps)\n{'='*64}")
        print(sub.to_string(index=False,
              columns=["symbol","n","fade_winrate","fade_gross_bps","fade_net_bps","cont_gross_bps"],
              float_format=lambda x: f"{x:7.2f}"))
        print(f"  POOLED  n={N}  fade_WR={wr:.1f}%  gross={gross:+.2f}bps  "
              f"NET={net:+.2f}bps  pairs_net_positive={pos_pairs}/{len(sub)}")


if __name__ == "__main__":
    main()
