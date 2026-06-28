#!/usr/bin/env python3
"""Study target quality for causal structure direction events.

This is not a full strategy backtest. It asks:

    Given a structure direction event, structural stop, and forward horizon,
    how often does price reach 0.5R/1R/1.5R/2R/3R before invalidation?
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
TARGETS_R = [0.5, 1.0, 1.5, 2.0, 3.0]


def asset_meta(symbol: str) -> dict[str, float | str]:
    if symbol == "XAUUSD":
        return {"asset_type": "commodity", "pip_size": 0.1}
    if symbol == "NAS100":
        return {"asset_type": "index", "pip_size": 1.0}
    if symbol == "GBPJPY":
        return {"asset_type": "forex", "pip_size": 0.01}
    return {"asset_type": "forex", "pip_size": 0.0001}


def session_name(ts: pd.Timestamp) -> str:
    hour = ts.hour
    if 7 <= hour < 10:
        return "london_open"
    if 13 <= hour < 16:
        return "ny_open"
    if 0 <= hour < 7:
        return "asia"
    return "other"


def first_finite(*values) -> float:
    for value in values:
        try:
            f = float(value)
        except Exception:
            continue
        if np.isfinite(f):
            return f
    return float("nan")


def add_event(events: list[dict], i: int, row: pd.Series, predictor: str, direction: int, htf: str | None) -> None:
    events.append(
        {
            "i": i,
            "ts": row["ts"],
            "predictor": predictor,
            "direction": "long" if direction > 0 else "short",
            "dir_sign": direction,
            "session": session_name(pd.Timestamp(row["ts"])),
            "htf_regime": htf or "neutral",
            "last_swing_low": row.get("last_swing_low"),
            "last_swing_high": row.get("last_swing_high"),
            "long_structural_sl": row.get("long_structural_sl"),
            "short_structural_sl": row.get("short_structural_sl"),
        }
    )


def build_events(st: pd.DataFrame, htf_st: pd.DataFrame | None) -> pd.DataFrame:
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
        regime = str(row["regime"])
        htf = str(htf_aligned[i]) if htf_aligned is not None else "neutral"
        if regime == "bull":
            add_event(events, i, row, "entry_regime_bull", +1, htf)
        elif regime == "bear":
            add_event(events, i, row, "entry_regime_bear", -1, htf)

        if htf == "bull":
            add_event(events, i, row, "htf_regime_bull", +1, htf)
        elif htf == "bear":
            add_event(events, i, row, "htf_regime_bear", -1, htf)
        if regime == "bull" and htf == "bull":
            add_event(events, i, row, "entry_plus_htf_bull", +1, htf)
        elif regime == "bear" and htf == "bear":
            add_event(events, i, row, "entry_plus_htf_bear", -1, htf)

        if bool(row["bos_up"]):
            add_event(events, i, row, "bos_up", +1, htf)
        if bool(row["bos_down"]):
            add_event(events, i, row, "bos_down", -1, htf)
        if bool(row["choch_up"]):
            add_event(events, i, row, "choch_up", +1, htf)
        if bool(row["choch_down"]):
            add_event(events, i, row, "choch_down", -1, htf)
        if bool(row["sweep_low"]):
            add_event(events, i, row, "sweep_low_reversal", +1, htf)
            add_event(events, i, row, "sweep_low_continuation", -1, htf)
        if bool(row["sweep_high"]):
            add_event(events, i, row, "sweep_high_reversal", -1, htf)
            add_event(events, i, row, "sweep_high_continuation", +1, htf)

    return pd.DataFrame(events)


def event_profile(df: pd.DataFrame, event: pd.Series, horizon: int, buffer: float) -> dict | None:
    i = int(event["i"])
    if i + 1 >= len(df):
        return None
    end = min(len(df), i + horizon + 1)
    entry = float(df.at[i, "close"])
    direction = int(event["dir_sign"])
    if direction > 0:
        sl = min(
            first_finite(event.get("long_structural_sl"), event.get("last_swing_low"), df.at[i, "low"]) - buffer,
            float(df.at[i, "low"]) - buffer,
        )
        risk = entry - sl
    else:
        sl = max(
            first_finite(event.get("short_structural_sl"), event.get("last_swing_high"), df.at[i, "high"]) + buffer,
            float(df.at[i, "high"]) + buffer,
        )
        risk = sl - entry
    if not np.isfinite(risk) or risk <= 0:
        return None

    future = df.iloc[i + 1 : end]
    if future.empty:
        return None
    if direction > 0:
        mfe_r = float(((future["high"].max() - entry) / risk))
        mae_r = float(((entry - future["low"].min()) / risk))
        close_r = float((future.iloc[-1]["close"] - entry) / risk)
    else:
        mfe_r = float(((entry - future["low"].min()) / risk))
        mae_r = float(((future["high"].max() - entry) / risk))
        close_r = float((entry - future.iloc[-1]["close"]) / risk)

    out = {
        "risk_price": risk,
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "close_r": close_r,
    }
    highs = future["high"].to_numpy(dtype=float)
    lows = future["low"].to_numpy(dtype=float)
    for target in TARGETS_R:
        if direction > 0:
            target_price = entry + target * risk
            target_hit = highs >= target_price
            stop_hit = lows <= sl
        else:
            target_price = entry - target * risk
            target_hit = lows <= target_price
            stop_hit = highs >= sl
        target_idx = int(np.argmax(target_hit)) if target_hit.any() else -1
        stop_idx = int(np.argmax(stop_hit)) if stop_hit.any() else -1
        hit_before_stop = target_idx >= 0 and (stop_idx < 0 or target_idx < stop_idx)
        stopped_first = stop_idx >= 0 and (target_idx < 0 or stop_idx <= target_idx)
        residual = max(-1.0, min(target, close_r))
        out[f"hit_{target:g}r"] = bool(hit_before_stop)
        out[f"outcome_{target:g}r"] = float(target if hit_before_stop else (-1.0 if stopped_first else residual))
    return out


def run_symbol(
    symbol: str,
    days: int,
    tf: str,
    htf_tf: str,
    horizon: int,
    left: int,
    right: int,
    predictors: set[str],
    sessions: set[str],
) -> pd.DataFrame:
    meta = asset_meta(symbol)
    df = load_data(symbol, tf, days=days, asset_type=str(meta["asset_type"]))
    if df.empty:
        return pd.DataFrame()
    cfg = StructureConfig(left=left, right=right)
    st = build_structure_index(df, cfg)
    htf_df = load_data(symbol, htf_tf, days=days + 14, asset_type=str(meta["asset_type"]))
    htf_st = build_structure_index(htf_df, cfg) if not htf_df.empty else None
    events = build_events(st, htf_st)
    if events.empty:
        return pd.DataFrame()
    if predictors:
        events = events[events["predictor"].isin(predictors)]
    if sessions:
        events = events[events["session"].isin(sessions)]

    buffer = 2.0 * float(meta["pip_size"])
    rows = []
    for event in events.itertuples(index=False):
        event_row = pd.Series(event._asdict())
        profile = event_profile(df, event_row, horizon, buffer)
        if profile is None:
            continue
        rows.append({"symbol": symbol, **event_row.to_dict(), **profile})
    return pd.DataFrame(rows)


def summarize(events: pd.DataFrame, min_n: int) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows = []
    for key, group in events.groupby(["symbol", "predictor", "direction", "session"]):
        row = {
            "symbol": key[0],
            "predictor": key[1],
            "direction": key[2],
            "session": key[3],
            "n": len(group),
            "mfe_med_r": group["mfe_r"].median(),
            "mfe_p75_r": group["mfe_r"].quantile(0.75),
            "mae_med_r": group["mae_r"].median(),
            "close_avg_r": group["close_r"].mean(),
        }
        for target in TARGETS_R:
            hit_col = f"hit_{target:g}r"
            out_col = f"outcome_{target:g}r"
            row[f"hit_{target:g}r_pct"] = group[hit_col].mean() * 100.0
            row[f"exp_{target:g}r"] = group[out_col].mean()
        rows.append(row)
    out = pd.DataFrame(rows)
    out = out[out["n"] >= min_n].copy()
    if out.empty:
        return out
    return out.sort_values(["exp_1r", "exp_1.5r", "n"], ascending=[False, False, False])


def main() -> None:
    parser = argparse.ArgumentParser(description="Structure target quality study")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--tf", default="5")
    parser.add_argument("--htf-tf", default="240")
    parser.add_argument("--horizon", type=int, default=24, help="Forward bars")
    parser.add_argument("--left", type=int, default=2)
    parser.add_argument("--right", type=int, default=2)
    parser.add_argument("--predictors", default="", help="Comma-separated predictor names")
    parser.add_argument("--sessions", default="", help="Comma-separated session names")
    parser.add_argument("--tag", default="structure_target_study")
    parser.add_argument("--min-n", type=int, default=30)
    args = parser.parse_args()

    predictors = {s.strip() for s in args.predictors.split(",") if s.strip()}
    sessions = {s.strip() for s in args.sessions.split(",") if s.strip()}
    frames = []
    for symbol in [s.strip().upper() for s in args.symbols.split(",") if s.strip()]:
        print(f"{symbol}...", flush=True)
        frame = run_symbol(
            symbol=symbol,
            days=args.days,
            tf=args.tf,
            htf_tf=args.htf_tf,
            horizon=args.horizon,
            left=args.left,
            right=args.right,
            predictors=predictors,
            sessions=sessions,
        )
        if not frame.empty:
            frames.append(frame)

    if not frames:
        raise SystemExit("No target-study rows generated")
    events = pd.concat(frames, ignore_index=True)
    events_path = OUT / f"{args.tag}_events.csv"
    summary_path = OUT / f"{args.tag}.csv"
    events.to_csv(events_path, index=False)
    summary = summarize(events, args.min_n)
    summary.to_csv(summary_path, index=False)
    print(f"Saved {summary_path} rows={len(summary)}")
    print(f"Saved {events_path} rows={len(events)}")
    if not summary.empty:
        cols = [
            "symbol",
            "predictor",
            "direction",
            "session",
            "n",
            "mfe_med_r",
            "mae_med_r",
            "hit_1r_pct",
            "exp_1r",
            "hit_1.5r_pct",
            "exp_1.5r",
            "hit_2r_pct",
            "exp_2r",
        ]
        print(summary[cols].head(40).to_string(index=False))


if __name__ == "__main__":
    main()
