#!/usr/bin/env python3
"""Measure whether causal structure state predicts forward direction.

This is not a strategy backtest. It answers a simpler question:

    If structure says bull/bear at time T, does price actually move that way
    over the next N bars often enough to justify using it as a direction gate?
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

from backtesting.engine.data import load_data  # noqa: E402
from backtesting.features.structure import StructureConfig, build_structure_index  # noqa: E402

OUT = ROOT / "backtesting" / "results"
OUT.mkdir(parents=True, exist_ok=True)

DEFAULT_SYMBOLS = ["XAUUSD", "NAS100", "GBPJPY", "GBPUSD", "EURUSD", "GBPAUD"]
HORIZONS = [6, 12, 24, 48]  # 5m bars: 30m, 1h, 2h, 4h


def asset_type_for(symbol: str) -> str:
    if symbol == "XAUUSD":
        return "commodity"
    if symbol == "NAS100":
        return "index"
    return "forex"


def session_name(ts: pd.Timestamp) -> str:
    hour = ts.hour
    if 7 <= hour < 10:
        return "london_open"
    if 13 <= hour < 16:
        return "ny_open"
    if 0 <= hour < 7:
        return "asia"
    return "other"


def signed_forward_return(close: np.ndarray, i: int, direction: int, horizon: int) -> float:
    j = i + horizon
    if j >= len(close):
        return np.nan
    return direction * (close[j] - close[i]) / close[i]


def t_stat(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if len(values) < 5:
        return 0.0
    std = values.std(ddof=1)
    if std == 0:
        return 0.0
    return float(values.mean() / (std / np.sqrt(len(values))))


def add_event(events: list[dict], i: int, ts, predictor: str, direction: int, session: str) -> None:
    events.append(
        {
            "i": i,
            "ts": ts,
            "predictor": predictor,
            "direction": "long" if direction > 0 else "short",
            "dir_sign": direction,
            "session": session,
        }
    )


def build_events(df: pd.DataFrame, st: pd.DataFrame, htf_st: pd.DataFrame | None) -> pd.DataFrame:
    events: list[dict] = []
    htf_aligned = None
    if htf_st is not None and not htf_st.empty:
        htf_aligned = pd.merge_asof(
            st[["ts"]].sort_values("ts"),
            htf_st[["known_after_ts", "regime"]].sort_values("known_after_ts"),
            left_on="ts",
            right_on="known_after_ts",
            direction="backward",
        )["regime"].fillna("neutral").to_numpy(dtype=object)

    for i, row in st.iterrows():
        ts = row["ts"]
        session = session_name(ts)
        regime = str(row["regime"])
        if regime == "bull":
            add_event(events, i, ts, "entry_regime_bull", +1, session)
        elif regime == "bear":
            add_event(events, i, ts, "entry_regime_bear", -1, session)

        if htf_aligned is not None:
            htf = str(htf_aligned[i])
            if htf == "bull":
                add_event(events, i, ts, "htf_regime_bull", +1, session)
            elif htf == "bear":
                add_event(events, i, ts, "htf_regime_bear", -1, session)
            if regime == "bull" and htf == "bull":
                add_event(events, i, ts, "entry_plus_htf_bull", +1, session)
            elif regime == "bear" and htf == "bear":
                add_event(events, i, ts, "entry_plus_htf_bear", -1, session)

        if bool(row["bos_up"]):
            add_event(events, i, ts, "bos_up", +1, session)
        if bool(row["bos_down"]):
            add_event(events, i, ts, "bos_down", -1, session)
        if bool(row["choch_up"]):
            add_event(events, i, ts, "choch_up", +1, session)
        if bool(row["choch_down"]):
            add_event(events, i, ts, "choch_down", -1, session)
        if bool(row["sweep_low"]):
            add_event(events, i, ts, "sweep_low_reversal", +1, session)
            add_event(events, i, ts, "sweep_low_continuation", -1, session)
        if bool(row["sweep_high"]):
            add_event(events, i, ts, "sweep_high_reversal", -1, session)
            add_event(events, i, ts, "sweep_high_continuation", +1, session)

    return pd.DataFrame(events)


def summarize(symbol: str, df: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    close = df["close"].to_numpy(dtype=float)
    rows = []
    keys = ["predictor", "direction", "session"]
    for key, group in events.groupby(keys):
        row = {"symbol": symbol, **dict(zip(keys, key)), "n": len(group)}
        for h in HORIZONS:
            rets = np.array(
                [signed_forward_return(close, int(r.i), int(r.dir_sign), h) for r in group.itertuples()],
                dtype=float,
            )
            rets = rets[np.isfinite(rets)]
            row[f"acc_{h}b"] = float((rets > 0).mean() * 100.0) if len(rets) else 0.0
            row[f"avg_ret_bps_{h}b"] = float(rets.mean() * 10_000.0) if len(rets) else 0.0
            row[f"t_{h}b"] = t_stat(rets)
        rows.append(row)
    return pd.DataFrame(rows)


def run_symbol(symbol: str, days: int, tf: str, htf_tf: str, left: int, right: int) -> pd.DataFrame:
    asset_type = asset_type_for(symbol)
    df = load_data(symbol, tf, days=days, asset_type=asset_type)
    if df.empty:
        return pd.DataFrame()
    cfg = StructureConfig(left=left, right=right)
    st = build_structure_index(df, cfg)
    htf_df = load_data(symbol, htf_tf, days=days + 14, asset_type=asset_type)
    htf_st = build_structure_index(htf_df, cfg) if not htf_df.empty else None
    events = build_events(df, st, htf_st)
    return summarize(symbol, df, events)


def main() -> None:
    parser = argparse.ArgumentParser(description="Structure direction accuracy")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--tf", default="5")
    parser.add_argument("--htf-tf", default="240")
    parser.add_argument("--left", type=int, default=2)
    parser.add_argument("--right", type=int, default=2)
    parser.add_argument("--tag", default="structure_direction_accuracy")
    parser.add_argument("--min-n", type=int, default=30)
    args = parser.parse_args()

    frames = []
    for symbol in [s.strip().upper() for s in args.symbols.split(",") if s.strip()]:
        print(f"{symbol}...", flush=True)
        out = run_symbol(symbol, args.days, args.tf, args.htf_tf, args.left, args.right)
        if not out.empty:
            frames.append(out)

    if not frames:
        raise SystemExit("No direction accuracy rows generated")
    result = pd.concat(frames, ignore_index=True)
    path = OUT / f"{args.tag}.csv"
    result.to_csv(path, index=False)
    print(f"Saved {path} rows={len(result)}")

    display = result[result["n"] >= args.min_n].copy()
    display["abs_t_24b"] = display["t_24b"].abs()
    cols = [
        "symbol",
        "predictor",
        "direction",
        "session",
        "n",
        "acc_12b",
        "avg_ret_bps_12b",
        "t_12b",
        "acc_24b",
        "avg_ret_bps_24b",
        "t_24b",
    ]
    print(display.sort_values(["abs_t_24b", "n"], ascending=[False, False])[cols].head(40).to_string(index=False))


if __name__ == "__main__":
    main()
