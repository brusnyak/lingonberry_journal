#!/usr/bin/env python3
"""Costed EMA trend-pullback lab across FX/XAU."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.engine.data import load_data  # noqa: E402
from backtesting.signal_lab import ACCOUNT_SIZE, CostSpec, OUT, first_hit_outcome_costed, spec_for  # noqa: E402

DEFAULT_SYMBOLS = [
    "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDUSD",
    "CADCHF", "CADJPY", "CHFJPY",
    "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPUSD",
    "USDCAD", "USDCHF", "XAUUSD",
]


def detect(symbol: str, days: int, ema_fast: int, ema_slow: int, lookback: int, rr: float, hold_bars: int) -> pd.DataFrame:
    spec = spec_for(symbol)
    df = load_data(symbol, "5", days=days, asset_type=spec.asset_type)
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=ema_fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=ema_slow, adjust=False).mean()
    df["date"] = df["ts"].dt.date
    ts = df["ts"].to_numpy()
    dates = df["date"].to_numpy()
    close = df["close"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    ema_f = df["ema_fast"].to_numpy(dtype=float)
    ema_s = df["ema_slow"].to_numpy(dtype=float)
    roll_low = pd.Series(lows).rolling(lookback + 1).min().to_numpy(dtype=float)
    roll_high = pd.Series(highs).rolling(lookback + 1).max().to_numpy(dtype=float)
    bar_range = highs - lows
    range_med = pd.Series(bar_range).rolling(96).median().to_numpy(dtype=float)
    range_slow = pd.Series(bar_range).rolling(960).median().to_numpy(dtype=float)
    rows = []
    last_day_signal: dict[tuple[str, str], object] = {}

    for i in range(max(ema_slow, lookback) + 2, len(df) - hold_bars - 1):
        bar_ts = pd.Timestamp(ts[i])
        h = int(bar_ts.hour)
        session = "london" if 7 <= h < 10 else "ny" if 13 <= h < 16 else ""
        if not session:
            continue

        trend_long = ema_f[i] > ema_s[i] and close[i] > ema_s[i]
        trend_short = ema_f[i] < ema_s[i] and close[i] < ema_s[i]
        path = df.iloc[i + 1 : i + hold_bars + 1]
        if path.empty:
            continue

        # One long and one short setup per symbol/session/day.
        day = dates[i]
        entry = float(close[i])

        if trend_long and close[i - 1] < ema_f[i - 1] and entry > ema_f[i]:
            key = (session, "long")
            if last_day_signal.get(key) == day:
                continue
            stop = float(roll_low[i]) - spec.buffer
            if stop < entry:
                r = first_hit_outcome_costed(path, "long", entry, stop, int(rr), spec, CostSpec())
                rows.append(event_row(symbol, bar_ts, day, session, "long", entry, stop, rr, hold_bars, r, ema_fast, ema_slow, lookback, spec, ema_f, ema_s, range_med, range_slow, i))
                last_day_signal[key] = day

        if trend_short and close[i - 1] > ema_f[i - 1] and entry < ema_f[i]:
            key = (session, "short")
            if last_day_signal.get(key) == day:
                continue
            stop = float(roll_high[i]) + spec.buffer
            if stop > entry:
                r = first_hit_outcome_costed(path, "short", entry, stop, int(rr), spec, CostSpec())
                rows.append(event_row(symbol, bar_ts, day, session, "short", entry, stop, rr, hold_bars, r, ema_fast, ema_slow, lookback, spec, ema_f, ema_s, range_med, range_slow, i))
                last_day_signal[key] = day
    return pd.DataFrame(rows)


def event_row(symbol, ts, date, session, direction, entry, stop, rr, hold_bars, r, ema_fast, ema_slow, lookback, spec, ema_f, ema_s, range_med, range_slow, i) -> dict:
    stop_pips = abs(entry - stop) / spec.pip
    ema_gap_pips = abs(ema_f[i] - ema_s[i]) / spec.pip
    slope_48_pips = (ema_s[i] - ema_s[i - 48]) / spec.pip if i >= 48 else 0.0
    if direction == "short":
        slope_48_pips *= -1
    vol_ratio = range_med[i] / range_slow[i] if np.isfinite(range_med[i]) and np.isfinite(range_slow[i]) and range_slow[i] > 0 else np.nan
    return {
        "symbol": symbol,
        "ts": ts,
        "date": str(date),
        "hour": int(pd.Timestamp(ts).hour),
        "session": session,
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "stop_pips": stop_pips,
        "ema_gap_pips": ema_gap_pips,
        "slope_48_pips": slope_48_pips,
        "vol_ratio": vol_ratio,
        "rr": rr,
        "hold_bars": hold_bars,
        "trade_r": r,
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "lookback": lookback,
        "rule_id": f"{symbol}|{session}|{direction}|ema{ema_fast}_{ema_slow}|lb{lookback}|rr{rr}|h{hold_bars}",
    }


def account(events: pd.DataFrame, risk_pct: float, max_trades_per_day: int, daily_lockout_pct: float) -> dict:
    if events.empty:
        return {}
    events = events.sort_values("ts").drop_duplicates(["ts", "symbol"], keep="first")
    equity = ACCOUNT_SIZE
    peak = equity
    wins = 0
    taken = 0
    day_start = {}
    day_pnl = {}
    day_count = {}
    max_dd = 0.0
    max_daily_loss = 0.0
    for _, row in events.iterrows():
        day = str(pd.Timestamp(row["ts"]).date())
        day_start.setdefault(day, equity)
        day_count.setdefault(day, 0)
        if day_count[day] >= max_trades_per_day:
            continue
        day_loss = max(0.0, -day_pnl.get(day, 0.0) / day_start[day] * 100.0)
        if day_loss >= daily_lockout_pct:
            continue
        r = float(row["trade_r"])
        if not np.isfinite(r):
            continue
        pnl = ACCOUNT_SIZE * risk_pct * r
        equity += pnl
        day_pnl[day] = day_pnl.get(day, 0.0) + pnl
        day_count[day] += 1
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100.0)
        wins += int(pnl > 0)
        taken += 1
    for day, pnl in day_pnl.items():
        max_daily_loss = max(max_daily_loss, -pnl / day_start[day] * 100.0)
    return {
        "n": taken,
        "return_pct": (equity - ACCOUNT_SIZE) / ACCOUNT_SIZE * 100.0,
        "max_dd_pct": max_dd,
        "max_daily_loss_pct": max_daily_loss,
        "win_rate_pct": wins / max(taken, 1) * 100.0,
        "avg_r": events["trade_r"].mean(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="EMA trend-pullback costed lab.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=490)
    parser.add_argument("--tag", default="490d")
    parser.add_argument("--risk-pct", type=float, default=1.0)
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    rows = []
    configs = [
        (20, 100, 12, 1, 24),
        (20, 100, 12, 2, 24),
        (50, 200, 12, 1, 24),
        (50, 200, 12, 2, 24),
        (50, 200, 24, 1, 48),
        (50, 200, 24, 2, 48),
    ]
    frames = []
    for cfg in configs:
        ema_fast, ema_slow, lookback, rr, hold_bars = cfg
        for symbol in symbols:
            ev = detect(symbol, args.days, ema_fast, ema_slow, lookback, rr, hold_bars)
            if not ev.empty:
                frames.append(ev)
    events = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    events_path = OUT / f"trend_pullback_{args.tag}_events.csv"
    events.to_csv(events_path, index=False)

    group_cols = ["symbol", "session", "direction", "ema_fast", "ema_slow", "lookback", "rr", "hold_bars"]
    for key, g in events.groupby(group_cols):
        if len(g) < 20:
            continue
        metrics = account(g, args.risk_pct / 100.0, max_trades_per_day=2, daily_lockout_pct=3.0)
        split = g["ts"].min() + (g["ts"].max() - g["ts"].min()) * 0.6
        a = g[g["ts"] < split]["trade_r"]
        b = g[g["ts"] >= split]["trade_r"]
        rows.append(dict(zip(group_cols, key)) | metrics | {
            "n1": len(a),
            "n2": len(b),
            "avg1": a.mean(),
            "avg2": b.mean(),
            "wr1": (a > 0).mean() * 100,
            "wr2": (b > 0).mean() * 100,
        })
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary["score"] = summary["return_pct"] - summary["max_dd_pct"] * 2 + summary["win_rate_pct"] * 0.05
        summary = summary.sort_values("score", ascending=False)
    summary_path = OUT / f"trend_pullback_{args.tag}_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Saved {events_path} rows={len(events)}")
    print(f"Saved {summary_path} rows={len(summary)}")
    if not summary.empty:
        cols = group_cols + ["n", "return_pct", "max_dd_pct", "max_daily_loss_pct", "win_rate_pct", "avg_r", "avg1", "avg2", "wr1", "wr2", "score"]
        print(summary[cols].head(30).to_string(index=False))


if __name__ == "__main__":
    main()
