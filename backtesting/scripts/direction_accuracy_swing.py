#!/usr/bin/env python3
"""Direction accuracy at swing confirmation points — with context filters.

Tests whether structure labels + context filters (MA trend, multi-TF alignment,
displacement) predict forward direction at swing confirmations.

This fixes the original test's fatal flaw: testing every bar with stale regime
labels. Here we test only at swing confirmation bars — the moments when structure
says something new — with proper context features.

Structure label → prediction mapping (ICT-based):
  HH in bull: continuation up → expect up
  HL in bull: pullback done → expect up
  LH in bull: weakening → expect down
  HH in neutral/bear: trend high → expect reversion down
  LH in bear: rally done, trend resumes down → expect down
  LL in bear: continuation down → expect down
  HL in bear: first higher low → expect up
  LL in neutral/bull: trend low → expect reversion up
  1H: first high → expect reversion down
  1L: first low → expect reversion up

BOS/CHOCH events are tested separately.
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


def asset_type_for(symbol: str) -> str:
    if symbol == "XAUUSD":
        return "commodity"
    if symbol == "NAS100":
        return "index"
    return "forex"


def _signal_direction(label: str, regime: str) -> int:
    """+1 (expect up), -1 (expect down), or 0 (no signal)."""
    if label == "HH":
        return 1 if regime == "bull" else -1
    if label == "HL":
        return 1
    if label == "LH":
        return -1
    if label == "LL":
        return -1 if regime == "bear" else 1
    if label == "1H":
        return -1
    if label == "1L":
        return 1
    return 0


def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    """Simple EMA."""
    out = np.full_like(arr, np.nan)
    if len(arr) < period:
        return out
    alpha = 2.0 / (period + 1)
    out[period - 1] = arr[:period].mean()
    for i in range(period, len(arr)):
        out[i] = arr[i] * alpha + out[i - 1] * (1 - alpha)
    return out


def _align_htf_regime(base_ts: pd.Series, htf_df: pd.DataFrame) -> np.ndarray:
    """Forward-align HTF known_after_ts to base bar ts."""
    return (
        pd.merge_asof(
            base_ts.to_frame("ts").sort_values("ts"),
            htf_df[["known_after_ts", "regime"]].rename(columns={"known_after_ts": "ts"}).sort_values("ts"),
            on="ts",
            direction="backward",
        )["regime"]
        .fillna("neutral")
        .to_numpy(dtype=object)
    )


def analyze_symbol(
    symbol: str,
    days: int,
    left: int = 2,
    right: int = 2,
    min_swing_atr: float = 0.0,
) -> pd.DataFrame:
    """Generate per-event rows for one symbol with context features."""
    atype = asset_type_for(symbol)
    df = load_data(symbol, "60", days=days + 7, asset_type=atype)
    if df.empty:
        print(f"  WARN: no data for {symbol}", file=sys.stderr)
        return pd.DataFrame()

    # Load 4h for multi-TF regime alignment
    htf = load_data(symbol, "240", days=days + 7, asset_type=atype)
    htf_st = build_structure_index(htf, StructureConfig(left=left, right=right)) if not htf.empty else None

    cfg = StructureConfig(left=left, right=right, min_swing_atr=min_swing_atr)
    st = build_structure_index(df, cfg)
    close = df["close"].to_numpy(dtype=float)
    n = len(st)

    # Context features: price vs EMA(50)
    ema50 = _ema(close, 50)
    price_above_ema = close > ema50  # uptrend context

    # Multi-TF regime alignment
    htf_regime = None
    if htf_st is not None:
        htf_regime = _align_htf_regime(st["ts"], htf_st)

    events: list[dict] = []

    for i in range(n):
        is_swing = st.iloc[i]["swing_type"] != ""
        is_bos = bool(st.iloc[i]["bos_up"]) or bool(st.iloc[i]["bos_down"])

        if not is_swing and not is_bos:
            continue

        label = st.iloc[i]["structure_label"] if is_swing else ""
        swing_type = st.iloc[i]["swing_type"] if is_swing else ""
        regime = st.iloc[i]["regime"]
        signal_dir = 0

        if is_bos:
            if st.iloc[i]["bos_up"]:
                signal_dir = 1
            elif st.iloc[i]["bos_down"]:
                signal_dir = -1
        elif label:
            signal_dir = _signal_direction(label, regime)

        context_up = bool(price_above_ema[i]) if not np.isnan(ema50[i]) else None
        htf_r = htf_regime[i] if htf_regime is not None else "neutral"
        tf_confluence = regime == htf_r and regime in ("bull", "bear")
        displacement = abs(close[i] - st.iloc[i]["last_swing_high"]) / close[i] * 100_00  # bps from HH level

        bos_up = bool(st.iloc[i]["bos_up"])
        bos_down = bool(st.iloc[i]["bos_down"])
        choch_up = bool(st.iloc[i]["choch_up"])
        choch_down = bool(st.iloc[i]["choch_down"])

        event_row: dict = {
            "ts": st.iloc[i]["ts"],
            "label": label,
            "regime": regime,
            "signal_dir": signal_dir,
            "context_up": context_up,
            "ema50_dev_pct": float((close[i] - ema50[i]) / ema50[i] * 100) if not np.isnan(ema50[i]) else None,
            "htf_regime": htf_r,
            "tf_confluence": tf_confluence,
            "bos_up": bos_up,
            "bos_down": bos_down,
            "choch_up": choch_up,
            "choch_down": choch_down,
        }

        for h in HORIZONS:
            j = min(i + h, n - 1)
            if j <= i:
                continue
            fwd_ret = (close[j] - close[i]) / close[i]
            fwd_up = 1 if fwd_ret > 0 else 0
            correct = (signal_dir == 1 and fwd_up) or (signal_dir == -1 and not fwd_up)

            event_row[f"fwd_close_{h}"] = close[j]
            event_row[f"fwd_ret_{h}"] = fwd_ret
            event_row[f"fwd_up_{h}"] = fwd_up
            event_row[f"correct_{h}"] = int(correct)

        events.append(event_row)

    if not events:
        return pd.DataFrame()

    return pd.DataFrame(events)


def _flat_summary(results: pd.DataFrame,
                  group_fn,
                  group_col: str,
                  min_n: int = 2) -> pd.DataFrame:
    """Generic flat-row accuracy summary."""
    rows = []
    for _, event in results.iterrows():
        g = group_fn(event)
        if g is None:
            continue
        for h in HORIZONS:
            cc = f"correct_{h}"
            rc = f"fwd_ret_{h}"
            if cc not in results.columns or pd.isna(event.get(cc)):
                continue
            rows.append({
                group_col: g,
                "horizon": h,
                "correct": int(event[cc]),
                "fwd_ret_bps": event[rc] * 10_000,
            })

    if not rows:
        return pd.DataFrame()
    detail = pd.DataFrame(rows)

    summary_rows = []
    for (g, h), sub in detail.groupby([group_col, "horizon"]):
        if len(sub) < min_n:
            continue
        summary_rows.append({
            group_col: g,
            "horizon": h,
            "n": len(sub),
            "accuracy": round(sub["correct"].mean() * 100, 1),
            "avg_ret_bps": round(sub["fwd_ret_bps"].mean(), 2),
        })

    if not summary_rows:
        return pd.DataFrame()
    return pd.DataFrame(summary_rows).sort_values(["horizon", group_col])


def summarize_by_context(results: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Multiple summaries sliced by context features."""
    out = {}

    # --- By label + regime ---
    def by_label(row):
        if not row["label"]:
            return None
        return f"{row['regime']}_{row['label']}"
    out["by_label"] = _flat_summary(results, by_label, "label_group")

    # --- By BOS ---
    def by_bos(row):
        if row["bos_up"]:
            return "BOS_up"
        if row["bos_down"]:
            return "BOS_down"
        return None
    out["by_bos"] = _flat_summary(results, by_bos, "bos_group")

    # --- By regime ---
    def by_regime(row):
        return row["regime"]
    out["by_regime"] = _flat_summary(results, by_regime, "regime")

    # --- By signal type ---
    def by_sigtype(row):
        if row["bos_up"] or row["bos_down"]:
            return "bos"
        if row["choch_up"] or row["choch_down"]:
            return "choch"
        if row["label"]:
            if row["regime"] in ("bull", "bear"):
                return f"swing_in_{row['regime']}"
            return "swing_neutral"
        return "other"
    out["by_signal_type"] = _flat_summary(results, by_sigtype, "signal_type")

    # --- By MA context (price vs EMA50) ---
    def by_ma(row):
        if row["context_up"] is True:
            return "price_above_ema50"
        if row["context_up"] is False:
            return "price_below_ema50"
        return None
    out["by_ma_context"] = _flat_summary(results, by_ma, "ma_context")

    # --- By TF confluence (base + HTF regime agree) ---
    def by_confluence(row):
        if row["regime"] == row["htf_regime"] and row["regime"] in ("bull", "bear"):
            return f"confluence_{row['regime']}"
        if row["regime"] != row["htf_regime"] and row["regime"] in ("bull", "bear") and row["htf_regime"] in ("bull", "bear"):
            return f"conflict_{row['regime']}_vs_{row['htf_regime']}"
        if row["regime"] in ("bull", "bear"):
            return "base_only"
        return "neutral"
    out["by_tf_confluence"] = _flat_summary(results, by_confluence, "confluence_group")

    # --- By MA + label combo ---
    def by_ma_label(row):
        if not row["label"]:
            return None
        if row["context_up"] is True:
            return f"above_ema50_{row['regime']}_{row['label']}"
        if row["context_up"] is False:
            return f"below_ema50_{row['regime']}_{row['label']}"
        return None
    out["by_ma_label"] = _flat_summary(results, by_ma_label, "ma_label_group")

    # --- By TF confluence + label ---
    def by_tf_label(row):
        if not row["label"]:
            return None
        if row["regime"] == row["htf_regime"] and row["regime"] in ("bull", "bear"):
            return f"confluence_{row['regime']}_{row['label']}"
        return None
    out["by_tf_label"] = _flat_summary(results, by_tf_label, "tf_label_group")

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Direction accuracy at swing points")
    parser.add_argument("--symbols", default="GBPAUD")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--left", type=int, default=2)
    parser.add_argument("--right", type=int, default=2)
    parser.add_argument("--min-swing-atr", type=float, default=0.0)
    parser.add_argument("--min-n", type=int, default=5)
    parser.add_argument("--tag", default="direction_accuracy_swing")

    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    all_raw = []
    for symbol in symbols:
        print(f"{symbol} (60m, {args.days}d, left={args.left} right={args.right} min_swing_atr={args.min_swing_atr})...", flush=True)
        results = analyze_symbol(symbol, args.days, args.left, args.right, args.min_swing_atr)
        if results.empty:
            print(f"  SKIP: no swing events for {symbol}", file=sys.stderr)
            continue
        results["symbol"] = symbol
        raw_path = OUT / f"{args.tag}_{symbol}_raw.parquet"
        results.to_parquet(raw_path, index=False)
        print(f"  {len(results)} swing events -> {raw_path}")
        all_raw.append(results)

    if not all_raw:
        raise SystemExit("No results generated")

    combined = pd.concat(all_raw, ignore_index=True)

    summaries = summarize_by_context(combined)

    for name, report in summaries.items():
        if report.empty:
            print(f"\n  SKIP summary: {name} (empty)")
            continue
        report = report[report["n"] >= args.min_n].copy()
        path = OUT / f"{args.tag}_{name}.csv"
        report.to_csv(path, index=False)
        print(f"\n{'='*70}")
        print(f"  {name}")
        print(f"{'='*70}")
        print(report.to_string(index=False))

    print(f"\n{'='*70}")
    print(f"  TOTAL swing events: {len(combined)}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
