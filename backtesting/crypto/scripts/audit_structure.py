"""
Audit structure_lib components across crypto pairs.

Runs the full structure pipeline on each pair and reports:
- Pivots (HH/HL/LL/LH) count
- BOS/ChoCH events
- FVGs detected
- OBs detected
- Pools found
- Sweeps detected
- Pipeline speed

Usage:
    python -m backtesting.crypto.scripts.audit_structure
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pandas as pd

from backtesting.engine.data import load_data
from backtesting.structure_lib.swing import swing_points
from backtesting.structure_lib.labels import label_structure
from backtesting.structure_lib.fvg import detect_fvgs
from backtesting.structure_lib.ob import detect_order_blocks
from backtesting.structure_lib.sweep import detect_pools, detect_sweeps
from backtesting.structure_lib.trade_signals import generate_signals

# Diverse crypto pairs (low correlation, different volatility profiles)
CRYPTO_PAIRS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "XRPUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "SUIUSDT",
    "NEARUSDT",
]

TIMEFRAMES = ["5", "30"]
WINDOW = ("2026-03-01", "2026-03-31")  # newest window


def audit_pair(pair: str) -> dict:
    t0 = time.time()
    result: dict = {
        "pair": pair,
        "error": None,
        "pivots": 0,
        "bos": 0,
        "choch": 0,
        "fvgs": 0,
        "obs": 0,
        "pools": 0,
        "sweeps": 0,
        "signals": 0,
        "time_s": 0.0,
    }

    try:
        df30 = load_data(pair, "30", start=WINDOW[0], end=WINDOW[1],
                         asset_type="crypto")
    except Exception as e:
        result["error"] = f"load_data: {e}"
        result["time_s"] = time.time() - t0
        return result

    if df30.empty:
        result["error"] = "no data"
        result["time_s"] = time.time() - t0
        return result

    # Normalize
    df30 = df30.set_index("ts") if "ts" in df30.columns else df30.copy()
    df30.index = pd.DatetimeIndex(df30.index)
    df30 = df30.rename(columns=str.lower)

    t1 = time.time()
    result["time_s"] = t1 - t0

    # Structure pipeline
    try:
        swings, levels = swing_points(df30, swing_length=1, causal=True)
        labels = label_structure(df30, swings, levels)
        fvgs = detect_fvgs(df30)
        obs = detect_order_blocks(df30, labels)
        pools = detect_pools(df30, swings, levels)

        t2 = time.time()

        # Count pivots
        for lbl in labels["structure_label"]:
            if lbl in ("HH", "HL", "LL", "LH"):
                result["pivots"] += 1

        # Count BOS/ChoCH
        for _, row in labels.iterrows():
            for direction in ("bullish", "bearish"):
                bos_col = f"{direction}_bos"
                choch_col = f"{direction}_choch"
                if bos_col in row and row[bos_col]:
                    result["bos"] += 1
                if choch_col in row and row[choch_col]:
                    result["choch"] += 1

        result["fvgs"] = len(fvgs)
        result["obs"] = len(obs)
        result["pools"] = len(pools)

        sweeps_start = time.time()
        sweeps = detect_sweeps(df30, pools)
        sweep_time = time.time() - sweeps_start

        result["sweeps"] = len(sweeps)

        sig_start = time.time()
        signals = generate_signals(ohlc=df30, labels=labels, sweeps=sweeps,
                                   fvgs=fvgs, obs=obs, pools=pools, min_rr=1.5)
        sig_time = time.time() - sig_start

        result["signals"] = len(signals)
        result["time_s"] = time.time() - t0
        result["structure_time"] = round(t2 - t1, 3)
        result["sweep_time"] = round(sweep_time, 3)
        result["signal_time"] = round(sig_time, 3)

    except Exception as e:
        result["error"] = str(e)
        result["time_s"] = time.time() - t0
        return result

    return result


def main() -> None:
    print(f"Structure audit — {WINDOW[0]} to {WINDOW[1]}")
    hdr = f"{'Pair':<10} {'Pivots':>6} {'BOS':>4} {'ChoCH':>6} {'FVG':>5} {'OB':>4} {'Pool':>5} {'Swp':>6} {'Sig':>4} {'Time':>6}"
    print(hdr)
    print("-" * len(hdr))

    totals: dict[str, int | float] = {
        "pivots": 0, "bos": 0, "choch": 0, "fvgs": 0,
        "obs": 0, "pools": 0, "sweeps": 0, "signals": 0
    }
    results: list[dict] = []

    for pair in CRYPTO_PAIRS:
        r = audit_pair(pair)
        results.append(r)
        if r["error"]:
            print(f"{pair:<10} {'ERROR':>32} {r['error']}")
            continue

        p = r["pivots"]
        bos = r["bos"]
        choch = r["choch"]
        fvgs = r["fvgs"]
        obs = r["obs"]
        pools = r["pools"]
        sweeps = r["sweeps"]
        signals = r["signals"]
        t = round(r["time_s"], 2)

        totals["pivots"] += p  # type: ignore[operator]
        totals["bos"] += bos  # type: ignore[operator]
        totals["choch"] += choch  # type: ignore[operator]
        totals["fvgs"] += fvgs  # type: ignore[operator]
        totals["obs"] += obs  # type: ignore[operator]
        totals["pools"] += pools  # type: ignore[operator]
        totals["sweeps"] += sweeps  # type: ignore[operator]
        totals["signals"] += signals  # type: ignore[operator]

        print(f"{pair:<10} {p:>6} {bos:>4} {choch:>6} {fvgs:>5} {obs:>4} {pools:>5} {sweeps:>6} {signals:>4} {t:>5.1f}s")

    print("-" * len(hdr))
    t = totals
    print(f"{'TOTAL':<10} {t['pivots']:>6} {t['bos']:>4} {t['choch']:>6} {t['fvgs']:>5} {t['obs']:>4} {t['pools']:>5} {t['sweeps']:>6} {t['signals']:>4}")

    print()
    print("Pairs with structure (sorted by pivot count):")
    results_sorted = sorted(results, key=lambda r: r.get("pivots", 0), reverse=True)
    for r in results_sorted:
        if r["error"]:
            continue
        print(f"  {r['pair']:<10} {r['pivots']:>4} pivots, {r['bos']:>3} BOS, {r['choch']:>4} ChoCH, {r['fvgs']:>4} FVG, {r['obs']:>3} OB, {r['sweeps']:>5} sweeps, {r['signals']:>3} sigs, {r['time_s']:.1f}s")


if __name__ == "__main__":
    main()
