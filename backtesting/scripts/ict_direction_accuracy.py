#!/usr/bin/env python3
"""Triple-barrier direction accuracy for strict ICT structure."""
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
from backtesting.features.ict_structure import IctStructureConfig, build_ict_structure_index  # noqa: E402

OUT = ROOT / "backtesting" / "results"
OUT.mkdir(parents=True, exist_ok=True)
TARGETS_R = [1.0, 1.5, 2.0]


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


def add_event(events: list[dict], st: pd.DataFrame, i: int, predictor: str, direction: int) -> None:
    row = st.iloc[i]
    events.append(
        {
            "i": i,
            "ts": row["ts"],
            "predictor": predictor,
            "direction": "long" if direction > 0 else "short",
            "dir_sign": direction,
            "session": session_name(pd.Timestamp(row["ts"])),
            "protected_low": row.get("protected_low"),
            "protected_high": row.get("protected_high"),
            "last_hl": row.get("last_hl"),
            "last_lh": row.get("last_lh"),
        }
    )


def build_events(st: pd.DataFrame, state_stride: int) -> pd.DataFrame:
    events: list[dict] = []
    last_state_i = {"bullish": -10**9, "bearish": -10**9}
    for i, row in st.iterrows():
        if bool(row["bullish_bos"]):
            add_event(events, st, i, "bullish_bos", +1)
        if bool(row["bearish_bos"]):
            add_event(events, st, i, "bearish_bos", -1)

        state = str(row["ict_state"])
        if state == "bullish" and i - last_state_i[state] >= state_stride:
            add_event(events, st, i, "bullish_state", +1)
            last_state_i[state] = i
        elif state == "bearish" and i - last_state_i[state] >= state_stride:
            add_event(events, st, i, "bearish_state", -1)
            last_state_i[state] = i
    return pd.DataFrame(events)


def event_profile(df: pd.DataFrame, event: pd.Series, horizon: int, fallback_risk_bps: float) -> dict | None:
    i = int(event["i"])
    if i + 1 >= len(df):
        return None
    end = min(len(df), i + horizon + 1)
    future = df.iloc[i + 1 : end]
    if future.empty:
        return None

    entry = float(df.at[i, "close"])
    direction = int(event["dir_sign"])
    if direction > 0:
        stop = _first_finite(event.get("protected_low"), event.get("last_hl"))
        if not np.isfinite(stop) or stop >= entry:
            stop = entry * (1.0 - fallback_risk_bps / 10_000.0)
        risk = entry - stop
        mfe_r = float((future["high"].max() - entry) / risk)
        mae_r = float((entry - future["low"].min()) / risk)
        close_r = float((future.iloc[-1]["close"] - entry) / risk)
    else:
        stop = _first_finite(event.get("protected_high"), event.get("last_lh"))
        if not np.isfinite(stop) or stop <= entry:
            stop = entry * (1.0 + fallback_risk_bps / 10_000.0)
        risk = stop - entry
        mfe_r = float((entry - future["low"].min()) / risk)
        mae_r = float((future["high"].max() - entry) / risk)
        close_r = float((entry - future.iloc[-1]["close"]) / risk)

    if not np.isfinite(risk) or risk <= 0:
        return None

    out = {"risk_price": risk, "mfe_r": mfe_r, "mae_r": mae_r, "close_r": close_r}
    highs = future["high"].to_numpy(dtype=float)
    lows = future["low"].to_numpy(dtype=float)
    for target in TARGETS_R:
        if direction > 0:
            target_hit = highs >= entry + target * risk
            stop_hit = lows <= stop
        else:
            target_hit = lows <= entry - target * risk
            stop_hit = highs >= stop
        target_idx = int(np.argmax(target_hit)) if target_hit.any() else -1
        stop_idx = int(np.argmax(stop_hit)) if stop_hit.any() else -1
        hit_before_stop = target_idx >= 0 and (stop_idx < 0 or target_idx < stop_idx)
        stopped_first = stop_idx >= 0 and (target_idx < 0 or stop_idx <= target_idx)
        residual = max(-1.0, min(target, close_r))
        out[f"hit_{target:g}r"] = bool(hit_before_stop)
        out[f"outcome_{target:g}r"] = float(target if hit_before_stop else (-1.0 if stopped_first else residual))
    return out


def run_symbol(symbol: str, days: int, tf: str, left: int, right: int, horizon: int, state_stride: int) -> pd.DataFrame:
    df = load_data(symbol, tf, days=days, asset_type=asset_type_for(symbol))
    if df.empty:
        return pd.DataFrame()
    st = build_ict_structure_index(df, IctStructureConfig(left=left, right=right))
    events = build_events(st, state_stride=state_stride)
    rows = []
    for event in events.itertuples(index=False):
        event_row = pd.Series(event._asdict())
        profile = event_profile(df, event_row, horizon=horizon, fallback_risk_bps=20.0)
        if profile is not None:
            rows.append({"symbol": symbol, **event_row.to_dict(), **profile})
    return pd.DataFrame(rows)


def summarize(events: pd.DataFrame, min_n: int) -> pd.DataFrame:
    rows = []
    if events.empty:
        return pd.DataFrame()
    for key, group in events.groupby(["symbol", "predictor", "direction", "session"]):
        row = {
            "symbol": key[0],
            "predictor": key[1],
            "direction": key[2],
            "session": key[3],
            "n": len(group),
            "mfe_med_r": group["mfe_r"].median(),
            "mae_med_r": group["mae_r"].median(),
            "close_avg_r": group["close_r"].mean(),
        }
        for target in TARGETS_R:
            row[f"hit_{target:g}r_pct"] = group[f"hit_{target:g}r"].mean() * 100.0
            row[f"exp_{target:g}r"] = group[f"outcome_{target:g}r"].mean()
        rows.append(row)
    out = pd.DataFrame(rows)
    out = out[out["n"] >= min_n].copy()
    if out.empty:
        return out
    return out.sort_values(["exp_1r", "exp_1.5r", "n"], ascending=[False, False, False])


def _first_finite(*values) -> float:
    for value in values:
        try:
            f = float(value)
        except Exception:
            continue
        if np.isfinite(f):
            return f
    return float("nan")


def main() -> None:
    parser = argparse.ArgumentParser(description="Strict ICT direction accuracy")
    parser.add_argument("--symbols", default="XAUUSD,NAS100,GBPJPY,GBPUSD,EURUSD,GBPAUD")
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--tf", default="5")
    parser.add_argument("--left", type=int, default=3)
    parser.add_argument("--right", type=int, default=3)
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--state-stride", type=int, default=12)
    parser.add_argument("--min-n", type=int, default=20)
    parser.add_argument("--tag", default="ict_direction_accuracy")
    args = parser.parse_args()

    frames = []
    for symbol in [s.strip().upper() for s in args.symbols.split(",") if s.strip()]:
        print(f"{symbol}...", flush=True)
        frame = run_symbol(symbol, args.days, args.tf, args.left, args.right, args.horizon, args.state_stride)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        raise SystemExit("No strict ICT direction events generated")
    events = pd.concat(frames, ignore_index=True)
    summary = summarize(events, args.min_n)
    events_path = OUT / f"{args.tag}_events.csv"
    summary_path = OUT / f"{args.tag}.csv"
    events.to_csv(events_path, index=False)
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
