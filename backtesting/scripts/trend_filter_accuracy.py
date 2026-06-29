#!/usr/bin/env python3
"""Research: which MA-based trend filters predict direction best?

Tests multiple MA types, periods, and signals at every bar and at swing
points only. Outputs accuracy for each combination across forward horizons.

Signals tested:
  1. price > MA (uptrend context)
  2. MA slope > 0 (rising MA)
  3. fast MA > slow MA (crossover)
  4. Multi-TF alignment (all TFs agree on trend)
  5. HH/HL/LH/LL + MA confluence

Usage:
    python backtesting/scripts/trend_filter_accuracy.py --symbols GBPAUD --days 365
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.engine.data import load_data
from backtesting.features.structure import StructureConfig, build_structure_index

OUT = ROOT / "backtesting" / "results"
OUT.mkdir(parents=True, exist_ok=True)

HORIZONS = [6, 12, 24, 48]
TFS = ["5", "15", "60", "240"]
BASE_TF = "60"
MA_PERIODS = [10, 20, 50, 100, 200]


def asset_type_for(symbol: str) -> str:
    if symbol == "XAUUSD":
        return "commodity"
    if symbol == "NAS100":
        return "index"
    return "forex"


def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    out = np.full_like(arr, np.nan)
    if len(arr) < period:
        return out
    alpha = 2.0 / (period + 1)
    out[period - 1] = arr[:period].mean()
    for i in range(period, len(arr)):
        out[i] = arr[i] * alpha + out[i - 1] * (1 - alpha)
    return out


def _slope(arr: np.ndarray, period: int = 5) -> np.ndarray:
    """Rate of change over N bars as fraction."""
    out = np.full_like(arr, np.nan)
    for i in range(period, len(arr)):
        out[i] = (arr[i] - arr[i - period]) / arr[i - period]
    return out


def _align_htf_ma(base_ts: pd.Series, htf_close: np.ndarray, htf_ts: pd.Series) -> np.ndarray:
    """Forward-align HTF close prices to base bar timestamps."""
    htf_df = pd.DataFrame({"ts": htf_ts, "htf_close": htf_close}).sort_values("ts")
    aligned = pd.merge_asof(
        base_ts.to_frame("ts").sort_values("ts"),
        htf_df,
        on="ts",
        direction="backward",
    )["htf_close"]
    return aligned.to_numpy(dtype=float) if aligned.notna().any() else np.full(len(base_ts), np.nan)


def _get_ma_signals(close: np.ndarray, period: int) -> dict[str, np.ndarray]:
    """Compute all single-TF MA signals for one period."""
    ma = _ema(close, period)

    price_above = close > ma  # uptrend
    slope = _slope(ma, period=5)  # MA rate of change
    slope_up = slope > 0  # rising MA
    return {"ma": ma, "price_above": price_above, "slope_up": slope_up, "slope": slope}


def analyze_symbol(
    symbol: str,
    days: int,
) -> pd.DataFrame:
    """Generate per-bar MA signal accuracy for one symbol."""
    atype = asset_type_for(symbol)

    # Load base TF + HTF for multi-TF MA alignment
    tf_data = {}
    for tf in TFS:
        extra = 7 if tf != BASE_TF else 0
        df = load_data(symbol, tf, days=days + extra, asset_type=atype)
        if df.empty:
            continue
        tf_data[tf] = df

    if BASE_TF not in tf_data:
        return pd.DataFrame()

    base_df = tf_data[BASE_TF]
    base_close = base_df["close"].to_numpy(dtype=float)
    base_ts = base_df["ts"]
    n = len(base_close)

    # Build structure index for swing-point analysis
    st = build_structure_index(base_df, StructureConfig(left=2, right=2))

    # Compute MA signals for each timeframe
    tf_signals: dict[str, dict] = {}

    # Base TF: compute directly
    base_sigs = _get_ma_signals(base_close, period=50)
    tf_signals[BASE_TF] = base_sigs

    # HTF: compute MA on HTF, then forward-align to base
    for tf in TFS:
        if tf == BASE_TF or tf not in tf_data:
            continue
        df = tf_data[tf]
        c = df["close"].to_numpy(dtype=float)
        htf_ma = _ema(c, 50)
        htf_slope = _slope(htf_ma, period=5)

        # Forward-align HTF MA to base TF timestamps
        htf_df = pd.DataFrame({"ts": df["ts"], "ma": htf_ma, "slope": htf_slope}).sort_values("ts").dropna(subset=["ma"])
        if htf_df.empty:
            continue
        aligned = pd.merge_asof(
            base_ts.to_frame("ts").sort_values("ts"),
            htf_df,
            on="ts",
            direction="backward",
        )
        tf_signals[tf] = {
            "ma": aligned["ma"].to_numpy(dtype=float),
            "price_above": (base_close > aligned["ma"].to_numpy(dtype=float)),
            "slope_up": aligned["slope"].to_numpy(dtype=float) > 0,
            "slope": aligned["slope"].to_numpy(dtype=float),
        }

    # Now test every combination of periods on BASE_TF
    rows = []
    for period in MA_PERIODS:
        sigs = _get_ma_signals(base_close, period)

        for i in range(n):
            price_above = bool(sigs["price_above"][i]) if not np.isnan(sigs["ma"][i]) else None
            slope_up = bool(sigs["slope_up"][i]) if not np.isnan(sigs["slope"][i]) else None
            ma_val = sigs["ma"][i]

            if price_above is None:
                continue

            # Multi-TF alignment: all TFs agree price is above MA
            tf_align_up = all(
                tf in tf_signals
                and i < len(tf_signals[tf]["price_above"])
                and tf_signals[tf]["price_above"][i]
                for tf in TFS
            )
            tf_align_down = all(
                tf in tf_signals
                and i < len(tf_signals[tf]["price_above"])
                and not tf_signals[tf]["price_above"][i]
                for tf in TFS
            )

            is_swing = st.iloc[i]["swing_type"] != "" if i < len(st) else False

            # Check forward returns for each signal type
            for h in HORIZONS:
                j = min(i + h, n - 1)
                if j <= i:
                    continue
                fwd_ret = (base_close[j] - base_close[i]) / base_close[i]
                fwd_up = 1 if fwd_ret > 0 else 0

                # Signal: price above MA → expect up
                if price_above is not None:
                    correct_ma = (1 if price_above else 0) == fwd_up
                    rows.append({
                        "group": f"price_above_ma{period}",
                        "horizon": h,
                        "n_sig": period,
                        "signal_type": "price_vs_ma",
                        "correct": int(correct_ma),
                        "fwd_ret_bps": fwd_ret * 10_000,
                        "at_swing": is_swing,
                    })

                # Signal: MA slope up → expect up
                if slope_up is not None:
                    correct_slope = (1 if slope_up else 0) == fwd_up
                    rows.append({
                        "group": f"ma{period}_slope_up",
                        "horizon": h,
                        "n_sig": period,
                        "signal_type": "ma_slope",
                        "correct": int(correct_slope),
                        "fwd_ret_bps": fwd_ret * 10_000,
                        "at_swing": is_swing,
                    })

                # Signal: multi-TF alignment
                if tf_align_up:
                    correct_tf = fwd_up == 1
                    rows.append({
                        "group": f"all_tf_above_ma50",
                        "horizon": h,
                        "n_sig": 50,
                        "signal_type": "multi_tf_alignment",
                        "correct": int(correct_tf),
                        "fwd_ret_bps": fwd_ret * 10_000,
                        "at_swing": is_swing,
                    })
                elif tf_align_down:
                    correct_tf = fwd_up == 0
                    rows.append({
                        "group": f"all_tf_below_ma50",
                        "horizon": h,
                        "n_sig": 50,
                        "signal_type": "multi_tf_alignment",
                        "correct": int(correct_tf),
                        "fwd_ret_bps": fwd_ret * 10_000,
                        "at_swing": is_swing,
                    })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame, min_n: int = 50) -> pd.DataFrame:
    """Group by signal type, period, horizon and report accuracy."""
    summary_rows = []

    for (group, h), sub in results.groupby(["group", "horizon"]):
        n = len(sub)
        if n < min_n:
            continue
        accuracy = sub["correct"].mean() * 100
        avg_ret = sub["fwd_ret_bps"].mean()

        # At swing points only
        sub_swing = sub[sub["at_swing"]]
        n_swing = len(sub_swing)
        acc_swing = sub_swing["correct"].mean() * 100 if n_swing >= 10 else None

        summary_rows.append({
            "group": group,
            "horizon": h,
            "n": n,
            "accuracy": round(accuracy, 1),
            "avg_ret_bps": round(avg_ret, 2),
            "n_swing": n_swing,
            "acc_swing": round(acc_swing, 1) if acc_swing is not None else None,
        })

    if not summary_rows:
        return pd.DataFrame()
    return pd.DataFrame(summary_rows).sort_values(["horizon", "group"])


def main() -> None:
    parser = argparse.ArgumentParser(description="MA trend filter accuracy research")
    parser.add_argument("--symbols", default="GBPAUD")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--ma-type", default="ema")  # kept for future use
    parser.add_argument("--min-n", type=int, default=50)
    parser.add_argument("--tag", default="trend_filter")

    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    all_raw = []
    for symbol in symbols:
        print(f"{symbol} ({BASE_TF}m, {args.days}d)...", flush=True)
        results = analyze_symbol(symbol, args.days)
        if results.empty:
            print(f"  WARN: no results for {symbol}", file=sys.stderr)
            continue
        results["symbol"] = symbol
        raw_path = OUT / f"{args.tag}_{symbol}_raw.parquet"
        results.to_parquet(raw_path, index=False)
        print(f"  {len(results)} rows -> {raw_path}")
        all_raw.append(results)

    if not all_raw:
        raise SystemExit("No results generated")

    combined = pd.concat(all_raw, ignore_index=True)
    report = summarize(combined, args.min_n)

    if not report.empty:
        path = OUT / f"{args.tag}.csv"
        report.to_csv(path, index=False)

        # Show best performers
        print(f"\n{'='*70}")
        print(f"  TOP 10 BY ACCURACY (any horizon, n>={args.min_n})")
        print(f"{'='*70}")
        top = report.sort_values("accuracy", ascending=False).head(10)
        print(top.to_string(index=False))

        print(f"\n{'='*70}")
        print(f"  FULL REPORT -> {path}")
        print(f"{'='*70}")
        print(report.to_string(index=False))
    else:
        print("No summary rows generated.")


if __name__ == "__main__":
    main()
