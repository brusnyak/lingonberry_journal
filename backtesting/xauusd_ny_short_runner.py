#!/usr/bin/env python3
"""Dedicated audit runner for the XAUUSD NY short prop candidate.

This is intentionally narrow. It verifies the candidate outside the broad lab:
one asset, one setup, explicit filters, deterministic costed exits, and
account/monthly reports.
"""
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
from backtesting.signal_lab import ACCOUNT_SIZE, CostSpec, OUT, spec_for  # noqa: E402


SYMBOL = "XAUUSD"
SESSION_START_UTC = 13
SESSION_END_UTC = 16
EMA_FAST = 20
EMA_SLOW = 100
LOOKBACK = 12
RR = 2.0
HOLD_BARS = 24
EMA_GAP_MIN_PIPS = 10.0
VOL_RATIO_MIN = 1.0
VOL_RATIO_MAX = 2.0
MAX_TRADES_PER_DAY = 2
DAILY_LOCKOUT_PCT = 3.0


def first_hit_detail(
    path: pd.DataFrame,
    entry_signal: float,
    stop: float,
    spec,
    costs: CostSpec,
) -> dict:
    entry_fill = entry_signal - costs.entry_spread_pips * spec.pip
    risk = abs(entry_fill - stop)
    if risk <= 0 or not np.isfinite(risk):
        return {}
    risk_pips = risk / spec.pip
    commission_r = costs.round_trip_commission_per_lot / max(risk_pips * spec.pip_value_per_lot, 1e-9)
    tp = entry_fill - RR * risk

    for _, bar in path.iterrows():
        high = float(bar["high"])
        low = float(bar["low"])
        sl_hit = high >= stop
        tp_hit = low <= tp
        if sl_hit:
            exit_fill = stop + (costs.sl_exit_spread_pips + costs.slippage_pips) * spec.pip
            return {
                "exit_ts": bar["ts"],
                "exit_reason": "sl",
                "entry_fill": entry_fill,
                "exit_fill": exit_fill,
                "target": tp,
                "r": (entry_fill - exit_fill) / risk - commission_r,
                "risk_pips": risk_pips,
                "commission_r": commission_r,
            }
        if tp_hit:
            exit_fill = tp + costs.tp_exit_spread_pips * spec.pip
            return {
                "exit_ts": bar["ts"],
                "exit_reason": "tp",
                "entry_fill": entry_fill,
                "exit_fill": exit_fill,
                "target": tp,
                "r": (entry_fill - exit_fill) / risk - commission_r,
                "risk_pips": risk_pips,
                "commission_r": commission_r,
            }

    last = path.iloc[-1]
    exit_fill = float(last["close"]) + costs.tp_exit_spread_pips * spec.pip
    return {
        "exit_ts": last["ts"],
        "exit_reason": "time",
        "entry_fill": entry_fill,
        "exit_fill": exit_fill,
        "target": tp,
        "r": (entry_fill - exit_fill) / risk - commission_r,
        "risk_pips": risk_pips,
        "commission_r": commission_r,
    }


def generate_trades(days: int) -> pd.DataFrame:
    spec = spec_for(SYMBOL)
    costs = CostSpec()
    df = load_data(SYMBOL, "5", days=days, asset_type=spec.asset_type)
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["date"] = df["ts"].dt.date
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    ema_fast = pd.Series(close).ewm(span=EMA_FAST, adjust=False).mean().to_numpy(dtype=float)
    ema_slow = pd.Series(close).ewm(span=EMA_SLOW, adjust=False).mean().to_numpy(dtype=float)
    roll_high = pd.Series(high).rolling(LOOKBACK + 1).max().to_numpy(dtype=float)
    bar_range = high - low
    range_med = pd.Series(bar_range).rolling(96).median().to_numpy(dtype=float)
    range_slow = pd.Series(bar_range).rolling(960).median().to_numpy(dtype=float)

    rows = []
    last_day = None
    start_i = max(EMA_SLOW, LOOKBACK, 960) + 2
    for i in range(start_i, len(df) - HOLD_BARS - 1):
        ts = pd.Timestamp(df["ts"].iloc[i])
        if not (SESSION_START_UTC <= ts.hour < SESSION_END_UTC):
            continue
        day = df["date"].iloc[i]
        if last_day == day:
            continue
        if not (ema_fast[i] < ema_slow[i] and close[i] < ema_slow[i]):
            continue
        if not (close[i - 1] > ema_fast[i - 1] and close[i] < ema_fast[i]):
            continue
        if range_slow[i] <= 0 or not np.isfinite(range_med[i]) or not np.isfinite(range_slow[i]):
            continue

        stop = float(roll_high[i]) + spec.buffer
        entry = float(close[i])
        stop_pips = abs(stop - entry) / spec.pip
        ema_gap_pips = abs(ema_fast[i] - ema_slow[i]) / spec.pip
        vol_ratio = range_med[i] / range_slow[i]
        slope_48_pips = -1.0 * (ema_slow[i] - ema_slow[i - 48]) / spec.pip
        if ema_gap_pips < EMA_GAP_MIN_PIPS:
            continue
        if not (VOL_RATIO_MIN <= vol_ratio <= VOL_RATIO_MAX):
            continue
        if stop <= entry:
            continue

        path = df.iloc[i + 1 : i + HOLD_BARS + 1]
        detail = first_hit_detail(path, entry, stop, spec, costs)
        if not detail:
            continue
        rows.append(
            {
                "symbol": SYMBOL,
                "ts": ts,
                "date": str(day),
                "hour": ts.hour,
                "entry_signal": entry,
                "stop": stop,
                "stop_pips": stop_pips,
                "ema_gap_pips": ema_gap_pips,
                "slope_48_pips": slope_48_pips,
                "vol_ratio": vol_ratio,
                "rr": RR,
                "hold_bars": HOLD_BARS,
                "exit_ts": detail["exit_ts"],
                "exit_reason": detail["exit_reason"],
                "entry_fill": detail["entry_fill"],
                "exit_fill": detail["exit_fill"],
                "target": detail["target"],
                "risk_pips": detail["risk_pips"],
                "commission_r": detail["commission_r"],
                "trade_r": detail["r"],
            }
        )
        last_day = day
    return pd.DataFrame(rows)


def account_report(trades: pd.DataFrame, risk_pct: float) -> tuple[dict, pd.DataFrame]:
    if trades.empty:
        return {}, pd.DataFrame()
    equity = ACCOUNT_SIZE
    peak = equity
    day_start = {}
    day_pnl = {}
    day_count = {}
    rows = []
    wins = 0
    max_dd = 0.0
    max_daily_loss = 0.0
    skipped_day_limit = 0
    skipped_lockout = 0
    for _, row in trades.sort_values("ts").iterrows():
        day = str(pd.Timestamp(row["ts"]).date())
        day_start.setdefault(day, equity)
        day_count.setdefault(day, 0)
        if day_count[day] >= MAX_TRADES_PER_DAY:
            skipped_day_limit += 1
            continue
        day_loss = max(0.0, -day_pnl.get(day, 0.0) / day_start[day] * 100.0)
        if day_loss >= DAILY_LOCKOUT_PCT:
            skipped_lockout += 1
            continue
        r = float(row["trade_r"])
        pnl = ACCOUNT_SIZE * risk_pct * r
        equity += pnl
        day_pnl[day] = day_pnl.get(day, 0.0) + pnl
        day_count[day] += 1
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100.0
        max_dd = max(max_dd, dd)
        wins += int(pnl > 0)
        out = row.to_dict()
        out.update({"pnl": pnl, "equity": equity, "dd_pct": dd})
        rows.append(out)

    for day, pnl in day_pnl.items():
        max_daily_loss = max(max_daily_loss, -pnl / day_start[day] * 100.0)
    executed = pd.DataFrame(rows)
    report = {
        "risk_pct": risk_pct * 100.0,
        "signals": int(len(trades)),
        "trades": int(len(executed)),
        "skipped_day_limit": skipped_day_limit,
        "skipped_daily_lockout": skipped_lockout,
        "return_pct": (equity - ACCOUNT_SIZE) / ACCOUNT_SIZE * 100.0,
        "max_dd_pct": max_dd,
        "max_daily_loss_pct": max_daily_loss,
        "win_rate_pct": wins / max(len(executed), 1) * 100.0,
        "avg_r": float(executed["trade_r"].mean()) if not executed.empty else 0.0,
        "max_r": float(executed["trade_r"].max()) if not executed.empty else 0.0,
        "min_r": float(executed["trade_r"].min()) if not executed.empty else 0.0,
    }
    return report, executed


def monthly_report(executed: pd.DataFrame, risk_pct: float) -> pd.DataFrame:
    if executed.empty:
        return pd.DataFrame()
    rows = []
    for period, group in executed.groupby(pd.Grouper(key="ts", freq="30D")):
        if group.empty:
            continue
        report, _ = account_report(group, risk_pct)
        rows.append({"period_start": period, **report})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit XAUUSD NY short candidate.")
    parser.add_argument("--days", type=int, default=490)
    parser.add_argument("--risk-pcts", default="0.45,0.55")
    parser.add_argument("--tag", default="xauusd_ny_short")
    args = parser.parse_args()

    trades = generate_trades(args.days)
    trades_path = OUT / f"{args.tag}_signals.csv"
    trades.to_csv(trades_path, index=False)
    print(f"Saved {trades_path} rows={len(trades)}")

    summary_rows = []
    for risk in [float(x.strip()) / 100.0 for x in args.risk_pcts.split(",") if x.strip()]:
        report, executed = account_report(trades, risk)
        summary_rows.append(report)
        executed_path = OUT / f"{args.tag}_{risk * 100:.2f}risk_trades.csv"
        monthly_path = OUT / f"{args.tag}_{risk * 100:.2f}risk_monthly.csv"
        executed.to_csv(executed_path, index=False)
        monthly_report(executed, risk).to_csv(monthly_path, index=False)
        print(f"Saved {executed_path} rows={len(executed)}")
        print(f"Saved {monthly_path}")
    summary = pd.DataFrame(summary_rows)
    summary_path = OUT / f"{args.tag}_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Saved {summary_path}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
