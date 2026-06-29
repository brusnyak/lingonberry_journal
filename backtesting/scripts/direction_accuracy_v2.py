#!/usr/bin/env python3
"""Enhanced direction accuracy: multi-timeframe confluence + displacement strength.

Measures whether structure + price action at time T predicts forward direction
over the next N bars. No strategy logic, no look-ahead.

Questions answered:
  1. Does multi-TF alignment improve accuracy over single TF?
  2. Does displacement strength filter improve accuracy?
  3. Which timeframes and confluence levels are worth trading?
  4. Can simple price action filters (body ratio, wick) improve results?
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

HORIZONS = [6, 12, 24, 48]  # bars on the base timeframe
TFS = ["5", "15", "60", "240"]
BASE_TF = "60"  # analysis base (all TFs aligned to this)


def asset_type_for(symbol: str) -> str:
    if symbol == "XAUUSD":
        return "commodity"
    if symbol == "NAS100":
        return "index"
    return "forex"


def session_of(ts: pd.Timestamp) -> str:
    h = ts.hour
    if 7 <= h < 10:
        return "london_open"
    if 13 <= h < 16:
        return "ny_open"
    if 0 <= h < 7:
        return "asia"
    return "other"


def align_htf_regime(st_base: pd.DataFrame, st_htf: pd.DataFrame) -> np.ndarray:
    """Forward-align HTF regime to base TF bars: use most recent known HTF label."""
    aligned = pd.merge_asof(
        st_base[["ts"]].sort_values("ts"),
        st_htf[["known_after_ts", "regime"]].sort_values("known_after_ts"),
        left_on="ts",
        right_on="known_after_ts",
        direction="backward",
    )["regime"].fillna("neutral").to_numpy(dtype=object)
    return aligned


def align_ltf_regime(st_base: pd.DataFrame, st_ltf: pd.DataFrame) -> np.ndarray:
    """Backward-align LTF regime: LTF bar ends at or before base bar, use its last label."""
    aligned = pd.merge_asof(
        st_base[["ts"]].sort_values("ts"),
        st_ltf[["ts", "regime"]].sort_values("ts"),
        left_on="ts",
        right_on="ts",
        direction="backward",
    )["regime"].fillna("neutral").to_numpy(dtype=object)
    return aligned


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add price action features to OHLCV DataFrame."""
    out = df.copy()
    open_v = out["open"].to_numpy(dtype=float)
    high_v = out["high"].to_numpy(dtype=float)
    low_v = out["low"].to_numpy(dtype=float)
    close_v = out["close"].to_numpy(dtype=float)

    body = np.abs(close_v - open_v)
    candle_range = high_v - low_v
    eps = 1e-10

    # Body ratio
    out["body_ratio"] = np.where(candle_range > eps, body / candle_range, 0.0)
    # Upper wick ratio
    out["upper_wick_ratio"] = np.where(
        candle_range > eps,
        np.where(close_v >= open_v, (high_v - close_v) / candle_range, (high_v - open_v) / candle_range),
        0.0,
    )
    # Lower wick ratio
    out["lower_wick_ratio"] = np.where(
        candle_range > eps,
        np.where(close_v >= open_v, (open_v - low_v) / candle_range, (close_v - low_v) / candle_range),
        0.0,
    )
    # Pin bar: wick >= 2x body, wick >= 2x other wick
    bull_pin = (
        (out["lower_wick_ratio"] >= 0.6)
        & (out["lower_wick_ratio"] >= 2 * out["upper_wick_ratio"])
    )
    bear_pin = (
        (out["upper_wick_ratio"] >= 0.6)
        & (out["upper_wick_ratio"] >= 2 * out["lower_wick_ratio"])
    )
    out["pin_bar"] = (bull_pin | bear_pin).astype(int)
    out["pin_bull"] = bull_pin.astype(int)
    out["pin_bear"] = bear_pin.astype(int)

    # Inside bar
    out["inside_bar"] = (
        (high_v <= np.roll(high_v, 1))
        & (low_v >= np.roll(low_v, 1))
    ).astype(int)

    # Bullish / bearish body
    out["bull_bar"] = (close_v > open_v).astype(int)
    out["bear_bar"] = (close_v < open_v).astype(int)
    out["doji"] = (body < 0.1 * candle_range).astype(int)

    # Range expansion
    prev_range = np.roll(candle_range, 1)
    out["range_expansion"] = (candle_range > 1.5 * prev_range).astype(int)

    # Displacement: distance from close to most recent HH/HL/LH/LL
    # (computed as fraction of recent ATR)
    atr_period = 14
    tr = np.maximum(
        high_v - low_v,
        np.maximum(np.abs(high_v - np.roll(close_v, 1)), np.abs(low_v - np.roll(close_v, 1))),
    )
    atr = pd.Series(tr).rolling(atr_period, min_periods=1).mean().to_numpy(dtype=float)
    out["atr"] = atr
    out["atr_pct"] = np.where(close_v > 0, atr / close_v * 100, 0.0)

    return out


def analyze_symbol(
    symbol: str,
    days: int,
    swing_left: int = 2,
    swing_right: int = 2,
) -> pd.DataFrame:
    """Run multi-timeframe direction accuracy analysis for one symbol."""
    atype = asset_type_for(symbol)

    # Load all timeframes
    tf_data = {}
    tf_structure = {}
    for tf in TFS:
        extra = 7 if tf != BASE_TF else 0  # extra buffer for alignment
        df = load_data(symbol, tf, days=days + extra, asset_type=atype)
        if df.empty:
            print(f"  WARN: no data for {symbol} {tf}m", file=sys.stderr)
            continue
        cfg = StructureConfig(left=swing_left, right=swing_right)
        st = build_structure_index(df, cfg)
        tf_data[tf] = df
        tf_structure[tf] = st

    if BASE_TF not in tf_structure:
        return pd.DataFrame()

    base_st = tf_structure[BASE_TF]
    base_df = tf_data[BASE_TF]
    base_close = base_df["close"].to_numpy(dtype=float)
    features = compute_features(base_df)
    n = len(base_st)

    # Align regime labels from each TF to the base
    regime_data: dict[str, np.ndarray] = {}
    for tf in TFS:
        if tf == BASE_TF:
            regime_data[tf] = base_st["regime"].to_numpy(dtype=object)
        elif tf not in tf_structure:
            continue
        elif int(tf) > int(BASE_TF):
            reg_vals = align_htf_regime(base_st, tf_structure[tf])
            regime_data[tf] = reg_vals
        else:
            reg_vals = align_ltf_regime(base_st, tf_structure[tf])
            regime_data[tf] = reg_vals

    # Build results per bar
    results = []
    for i in range(n):
        ts = base_st.iloc[i]["ts"]

        # Regimes per TF
        regimes = {}
        for tf in TFS:
            if tf in regime_data and i < len(regime_data[tf]):
                regimes[tf] = str(regime_data[tf][i])
            else:
                regimes[tf] = "neutral"

        # Count aligned timeframes
        bull_count = sum(1 for r in regimes.values() if r == "bull")
        bear_count = sum(1 for r in regimes.values() if r == "bear")
        aligned_count = max(bull_count, bear_count)
        majority_dir = 1 if bull_count > bear_count else (-1 if bear_count > bull_count else 0)
        unanimous = aligned_count == len(TFS)

        # Displacement from structure
        dis_bull = 0.0
        dis_bear = 0.0
        if regimes[BASE_TF] == "bull" or regimes[BASE_TF] == "bear":
            bos_up = bool(base_st.iloc[i]["bos_up"])
            bos_down = bool(base_st.iloc[i]["bos_down"])
            if bos_up:
                level = base_st.iloc[i]["bos_level"]
                if not np.isnan(level):
                    dis_bull = (base_close[i] - level) / level
            if bos_down:
                level = base_st.iloc[i]["bos_level"]
                if not np.isnan(level):
                    dis_bear = (level - base_close[i]) / base_close[i]

        # Check forward returns
        for h in HORIZONS:
            j = i + h
            if j >= n:
                continue
            fwd_ret = (base_close[j] - base_close[i]) / base_close[i]
            fwd_up = 1 if fwd_ret > 0 else 0

            results.append({
                "symbol": symbol,
                "ts": ts,
                "session": session_of(ts),
                "horizon": h,
                "fwd_ret_bps": round(fwd_ret * 10_000, 2),
                "fwd_up": fwd_up,
                # Per-TF regime
                **{f"regime_{tf}": regimes[tf] for tf in TFS},
                # Alignment metrics
                "aligned_count": aligned_count,
                "majority_dir": majority_dir,
                "unanimous": int(unanimous),
                # Price action
                "body_ratio": float(features.iloc[i]["body_ratio"]),
                "upper_wick_ratio": float(features.iloc[i]["upper_wick_ratio"]),
                "lower_wick_ratio": float(features.iloc[i]["lower_wick_ratio"]),
                "pin_bar": int(features.iloc[i]["pin_bar"]),
                "pin_bull": int(features.iloc[i]["pin_bull"]),
                "pin_bear": int(features.iloc[i]["pin_bear"]),
                "inside_bar": int(features.iloc[i]["inside_bar"]),
                "bull_bar": int(features.iloc[i]["bull_bar"]),
                "bear_bar": int(features.iloc[i]["bear_bar"]),
                "doji": int(features.iloc[i]["doji"]),
                "range_expansion": int(features.iloc[i]["range_expansion"]),
                "atr_pct": float(features.iloc[i]["atr_pct"]),
                # Displacement
                "displacement_bull": dis_bull,
                "displacement_bear": dis_bear,
            })

    return pd.DataFrame(results)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    """Produce aggregated accuracy report from per-bar results."""
    if results.empty:
        return pd.DataFrame()

    rows = []

    # --- By regime combination ---
    for horizon in HORIZONS:
        sub = results[results["horizon"] == horizon].copy()

        # Overall accuracy by alignment level
        for aligned_n in range(len(TFS) + 1):
            s = sub[sub["aligned_count"] == aligned_n]
            if len(s) < 10:
                continue
            rows.append({
                "group": f"aligned_{aligned_n}_of_{len(TFS)}",
                "horizon": horizon,
                "n": len(s),
                "accuracy": round(s["fwd_up"].mean() * 100, 1),
                "avg_ret_bps": round(s["fwd_ret_bps"].mean(), 2),
                "t_stat": round(float(s["fwd_ret_bps"].mean() / (s["fwd_ret_bps"].std(ddof=1) / np.sqrt(len(s))) if s["fwd_ret_bps"].std(ddof=1) > 0 else 0.0), 2),
            })

        # Unanimous
        s = sub[sub["unanimous"] == 1]
        if len(s) >= 10:
            rows.append({
                "group": "unanimous_all_TF",
                "horizon": horizon,
                "n": len(s),
                "accuracy": round(s["fwd_up"].mean() * 100, 1),
                "avg_ret_bps": round(s["fwd_ret_bps"].mean(), 2),
                "t_stat": round(float(s["fwd_ret_bps"].mean() / (s["fwd_ret_bps"].std(ddof=1) / np.sqrt(len(s))) if s["fwd_ret_bps"].std(ddof=1) > 0 else 0.0), 2),
            })

        # By specific TF combo
        for tf in TFS:
            for regime in ["bull", "bear"]:
                s = sub[sub[f"regime_{tf}"] == regime]
                if len(s) < 10:
                    continue
                rows.append({
                    "group": f"{tf}m_{regime}",
                    "horizon": horizon,
                    "n": len(s),
                    "accuracy": round(s["fwd_up"].mean() * 100, 1),
                    "avg_ret_bps": round(s["fwd_ret_bps"].mean(), 2),
                    "t_stat": round(float(s["fwd_ret_bps"].mean() / (s["fwd_ret_bps"].std(ddof=1) / np.sqrt(len(s))) if s["fwd_ret_bps"].std(ddof=1) > 0 else 0.0), 2),
                })

        # 4H + 1H confluence
        s = sub[(sub["regime_240"] == sub["regime_60"]) & (sub["regime_240"] != "neutral")]
        for regime in ["bull", "bear"]:
            ss = s[s["regime_240"] == regime]
            if len(ss) >= 10:
                rows.append({
                    "group": f"240+60m_{regime}",
                    "horizon": horizon,
                    "n": len(ss),
                    "accuracy": round(ss["fwd_up"].mean() * 100, 1),
                    "avg_ret_bps": round(ss["fwd_ret_bps"].mean(), 2),
                    "t_stat": round(float(ss["fwd_ret_bps"].mean() / (ss["fwd_ret_bps"].std(ddof=1) / np.sqrt(len(ss))) if ss["fwd_ret_bps"].std(ddof=1) > 0 else 0.0), 2),
                })

        # All bullish / all bearish
        s_all_bull = sub[(sub["regime_5"] == "bull") & (sub["regime_15"] == "bull") &
                         (sub["regime_60"] == "bull") & (sub["regime_240"] == "bull")]
        if len(s_all_bull) >= 10:
            rows.append({
                "group": "all_TF_bull",
                "horizon": horizon,
                "n": len(s_all_bull),
                "accuracy": round(s_all_bull["fwd_up"].mean() * 100, 1),
                "avg_ret_bps": round(s_all_bull["fwd_ret_bps"].mean(), 2),
                "t_stat": round(float(s_all_bull["fwd_ret_bps"].mean() / (s_all_bull["fwd_ret_bps"].std(ddof=1) / np.sqrt(len(s_all_bull))) if s_all_bull["fwd_ret_bps"].std(ddof=1) > 0 else 0.0), 2),
            })
        s_all_bear = sub[(sub["regime_5"] == "bear") & (sub["regime_15"] == "bear") &
                         (sub["regime_60"] == "bear") & (sub["regime_240"] == "bear")]
        if len(s_all_bear) >= 10:
            rows.append({
                "group": "all_TF_bear",
                "horizon": horizon,
                "n": len(s_all_bear),
                "accuracy": round(s_all_bear["fwd_up"].mean() * 100, 1),
                "avg_ret_bps": round(s_all_bear["fwd_ret_bps"].mean(), 2),
                "t_stat": round(float(s_all_bear["fwd_ret_bps"].mean() / (s_all_bear["fwd_ret_bps"].std(ddof=1) / np.sqrt(len(s_all_bear))) if s_all_bear["fwd_ret_bps"].std(ddof=1) > 0 else 0.0), 2),
            })

        # By displacement strength (BOS displacement)
        for col, label in [("displacement_bull", "bos_bull"), ("displacement_bear", "bos_bear")]:
            s = sub[sub[col] > 0]
            if len(s) < 10:
                continue
            # Split into quintiles by displacement strength
            s = s.copy()
            s["dis_rank"] = pd.qcut(s[col], q=5, labels=False, duplicates="drop")
            for q in sorted(s["dis_rank"].unique()):
                ss = s[s["dis_rank"] == q]
                if len(ss) < 5:
                    continue
                rows.append({
                    "group": f"{label}_Q{q+1}",
                    "horizon": horizon,
                    "n": len(ss),
                    "accuracy": round(ss["fwd_up"].mean() * 100, 1),
                    "avg_ret_bps": round(ss["fwd_ret_bps"].mean(), 2),
                    "t_stat": round(float(ss["fwd_ret_bps"].mean() / (ss["fwd_ret_bps"].std(ddof=1) / np.sqrt(len(ss))) if ss["fwd_ret_bps"].std(ddof=1) > 0 else 0.0), 2),
                })

        # By session
        for session in ["asia", "london_open", "ny_open", "other"]:
            s = sub[sub["session"] == session]
            if len(s) < 10:
                continue
            rows.append({
                "group": f"session_{session}",
                "horizon": horizon,
                "n": len(s),
                "accuracy": round(s["fwd_up"].mean() * 100, 1),
                "avg_ret_bps": round(s["fwd_ret_bps"].mean(), 2),
                "t_stat": round(float(s["fwd_ret_bps"].mean() / (s["fwd_ret_bps"].std(ddof=1) / np.sqrt(len(s))) if s["fwd_ret_bps"].std(ddof=1) > 0 else 0.0), 2),
            })

        # By session + 4H regime alignment
        for session in ["asia", "london_open", "ny_open"]:
            for regime in ["bull", "bear"]:
                s = sub[(sub["session"] == session) & (sub["regime_240"] == regime)]
                if len(s) < 10:
                    continue
                rows.append({
                    "group": f"240m_{regime}_session_{session}",
                    "horizon": horizon,
                    "n": len(s),
                    "accuracy": round(s["fwd_up"].mean() * 100, 1),
                    "avg_ret_bps": round(s["fwd_ret_bps"].mean(), 2),
                    "t_stat": round(float(s["fwd_ret_bps"].mean() / (s["fwd_ret_bps"].std(ddof=1) / np.sqrt(len(s))) if s["fwd_ret_bps"].std(ddof=1) > 0 else 0.0), 2),
                })

    report = pd.DataFrame(rows)
    report = report.sort_values(["horizon", "group"])
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Direction accuracy v2 — multi-TF confluence")
    parser.add_argument("--symbols", default="GBPAUD")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--swing-left", type=int, default=2)
    parser.add_argument("--swing-right", type=int, default=2)
    parser.add_argument("--min-n", type=int, default=10)
    parser.add_argument("--tag", default="direction_accuracy_v2")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    all_frames = []
    for symbol in symbols:
        print(f"{symbol}...", flush=True)
        results = analyze_symbol(symbol, args.days, args.swing_left, args.swing_right)
        if results.empty:
            print(f"  SKIP: no results for {symbol}", file=sys.stderr)
            continue
        # Save raw per-bar results
        raw_path = OUT / f"{args.tag}_{symbol}_raw.parquet"
        results.to_parquet(raw_path, index=False)
        print(f"  raw: {len(results)} rows -> {raw_path}")
        all_frames.append(results)

    if not all_frames:
        raise SystemExit("No results generated")

    combined = pd.concat(all_frames, ignore_index=True)
    report = summarize(combined)
    if report.empty:
        raise SystemExit("No summary rows generated")

    # Filter by min-n
    report = report[report["n"] >= args.min_n].copy()

    path = OUT / f"{args.tag}.csv"
    report.to_csv(path, index=False)
    print(f"\nSummary -> {path}")
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
