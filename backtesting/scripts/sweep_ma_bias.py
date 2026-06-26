"""
MA bias sweep — explore all MA types and lengths as directional filter.

Tests: does MA alignment predict next-bar direction better than random on 4H bars?
MA types: SMA, EMA, HMA, WMA, DEMA, TEMA, KAMA
Cascade: MA_fast > MA_slow > MA_trend → bullish, else bearish
Measures: directional accuracy on next 4H bar close

NOT selection: this is exploration only. Documents all results.
Run: python -m backtesting.scripts.sweep_ma_bias
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data

# ── MA implementations ────────────────────────────────────────────────────────

def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()

def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()

def wma(s: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)

def hma(s: pd.Series, n: int) -> pd.Series:
    half = max(1, n // 2)
    sqrt_n = max(1, int(np.sqrt(n)))
    return wma(2 * wma(s, half) - wma(s, n), sqrt_n)

def dema(s: pd.Series, n: int) -> pd.Series:
    e = ema(s, n)
    return 2 * e - ema(e, n)

def tema(s: pd.Series, n: int) -> pd.Series:
    e1 = ema(s, n)
    e2 = ema(e1, n)
    e3 = ema(e2, n)
    return 3 * e1 - 3 * e2 + e3

def kama(s: pd.Series, n: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    result = np.full(len(s), np.nan)
    arr = s.values
    for i in range(n, len(arr)):
        direction = abs(arr[i] - arr[i - n])
        volatility = np.sum(np.abs(np.diff(arr[i - n:i + 1])))
        er = direction / volatility if volatility > 0 else 0
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        result[i] = result[i - 1] * (1 - sc) + arr[i] * sc if not np.isnan(result[i - 1]) else arr[i]
    return pd.Series(result, index=s.index)


MA_FUNCS = {
    "SMA":  sma,
    "EMA":  ema,
    "WMA":  wma,
    "HMA":  hma,
    "DEMA": dema,
    "TEMA": tema,
    "KAMA": kama,
}

# Lengths to test for fast/slow/trend cascade
FAST_LENGTHS  = [9, 20, 21]
SLOW_LENGTHS  = [50, 55]
TREND_LENGTHS = [100, 200]

# ── Test pairs / windows ──────────────────────────────────────────────────────

PAIRS = [
    ("GBPAUD", "forex"),
    ("EURUSD", "forex"),
    ("XAUUSD", "commodity"),
]
WINDOWS = [
    ("2025-09-15", "2025-10-15"),
    ("2025-12-01", "2025-12-31"),
    ("2026-03-01", "2026-03-31"),
]


def directional_accuracy(df4h: pd.DataFrame, ma_fn, fast: int, slow: int, trend: int) -> dict:
    """
    Returns accuracy metrics for a 3-MA cascade on 4H closes.

    Signal: MA_fast > MA_slow > MA_trend → bullish, else bearish
    Target: did next 4H bar close HIGHER than current? (1=yes)

    Returns dict with: n, accuracy, bull_accuracy, bear_accuracy
    """
    close = df4h["close"].reset_index(drop=True)
    try:
        ma_f = ma_fn(close, fast)
        ma_s = ma_fn(close, slow)
        ma_t = ma_fn(close, trend)
    except Exception:
        return {}

    bull_signal = (ma_f > ma_s) & (ma_s > ma_t)
    bear_signal = (ma_f < ma_s) & (ma_s < ma_t)

    next_up = (close.shift(-1) > close)  # next bar closed higher

    valid = (bull_signal | bear_signal) & next_up.notna()
    if valid.sum() < 20:
        return {}

    v_signal = bull_signal[valid]
    v_target = next_up[valid]

    correct = (v_signal & v_target) | (~v_signal & ~v_target)
    bull_mask = v_signal
    bear_mask = ~v_signal

    return {
        "n":             int(valid.sum()),
        "accuracy":      float(correct.mean()),
        "bull_n":        int(bull_mask.sum()),
        "bull_acc":      float(v_target[bull_mask].mean()) if bull_mask.sum() > 0 else float("nan"),
        "bear_n":        int(bear_mask.sum()),
        "bear_acc":      float((~v_target)[bear_mask].mean()) if bear_mask.sum() > 0 else float("nan"),
    }


def main() -> None:
    # Load 4H data for all pairs across all windows combined (more bars = more power)
    all_results = []

    print("Loading 4H data...")
    pair_data: dict[str, pd.DataFrame] = {}
    for pair, asset_type in PAIRS:
        kw = {} if asset_type is None else {"asset_type": asset_type}
        df = load_data(pair, "240", start="2025-09-01", end="2026-05-23", **kw)
        if df.empty:
            print(f"  {pair}: NO DATA")
            continue
        pair_data[pair] = df
        print(f"  {pair}: {len(df)} bars ({df['ts'].min().date()} → {df['ts'].max().date()})")

    print(f"\nTesting {len(MA_FUNCS)} MA types × {len(FAST_LENGTHS)}×{len(SLOW_LENGTHS)}×{len(TREND_LENGTHS)} lengths × {len(pair_data)} pairs...")

    for ma_name, ma_fn in MA_FUNCS.items():
        for fast in FAST_LENGTHS:
            for slow in SLOW_LENGTHS:
                for trend in TREND_LENGTHS:
                    if fast >= slow or slow >= trend:
                        continue  # invalid cascade

                    pair_accs = []
                    for pair, df in pair_data.items():
                        res = directional_accuracy(df, ma_fn, fast, slow, trend)
                        if res:
                            pair_accs.append(res["accuracy"])

                    if not pair_accs:
                        continue

                    mean_acc = np.mean(pair_accs)
                    all_results.append({
                        "ma":    ma_name,
                        "fast":  fast,
                        "slow":  slow,
                        "trend": trend,
                        "pairs": len(pair_accs),
                        "acc":   round(mean_acc, 4),
                    })

    if not all_results:
        print("No results — check data loading")
        return

    rdf = pd.DataFrame(all_results).sort_values("acc", ascending=False)

    print(f"\n{'MA':<6} {'fast':>5} {'slow':>5} {'trend':>6} {'pairs':>6} {'acc%':>7}")
    print("-" * 40)
    for _, row in rdf.head(20).iterrows():
        print(f"{row['ma']:<6} {int(row['fast']):>5} {int(row['slow']):>5} {int(row['trend']):>6} {int(row['pairs']):>6} {row['acc']*100:>6.1f}%")

    print(f"\n--- Bottom 10 ---")
    for _, row in rdf.tail(10).iterrows():
        print(f"{row['ma']:<6} {int(row['fast']):>5} {int(row['slow']):>5} {int(row['trend']):>6} {int(row['pairs']):>6} {row['acc']*100:>6.1f}%")

    # Save full results
    out = Path(__file__).parent.parent / "reports" / "ma_bias_sweep.csv"
    out.parent.mkdir(exist_ok=True)
    rdf.to_csv(out, index=False)
    print(f"\nFull results: {out}")
    print(f"Total configs tested: {len(rdf)}")
    print(f"Baseline (random): 50.0%  |  Mean across all: {rdf['acc'].mean()*100:.1f}%")


if __name__ == "__main__":
    main()
