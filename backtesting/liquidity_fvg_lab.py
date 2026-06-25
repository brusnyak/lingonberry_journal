#!/usr/bin/env python3
"""5m liquidity sweep + FVG retest lab for FX prop research.

This is a research lab, not a live trader. It tests a strict intraday model:

1. London/NY wick sweep of Asian high/low or prior-day high/low.
2. Reclaim close back inside the swept level.
3. Same-direction displacement creates a 5m FVG within N bars.
4. Price retraces to FVG CE for entry.
5. Stop beyond sweep extreme. Fixed RR target, deterministic adverse costs.

The goal is fast iteration over 30-day prop windows with real R targets.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.engine.data import load_data  # noqa: E402
from backtesting.signal_lab import ACCOUNT_SIZE, AssetSpec, CostSpec, OUT, spec_for  # noqa: E402


DEFAULT_FX = [
    "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDUSD",
    "CADCHF", "CADJPY", "CHFJPY",
    "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPUSD",
    "USDCAD", "USDCHF",
]


@dataclass(frozen=True)
class Config:
    rr: float
    fvg_max_bars: int
    retest_bars: int
    hold_bars: int
    min_gap_pips: float
    min_disp_ratio: float
    min_stop_pips: float
    session: str

    @property
    def id(self) -> str:
        return (
            f"{self.session}|rr{self.rr:g}|fvg{self.fvg_max_bars}|"
            f"rt{self.retest_bars}|h{self.hold_bars}|gap{self.min_gap_pips:g}|"
            f"disp{self.min_disp_ratio:g}|stop{self.min_stop_pips:g}"
        )


def session_name(ts: pd.Timestamp) -> str:
    hour = ts.hour
    if 7 <= hour < 10:
        return "london"
    if 13 <= hour < 16:
        return "ny"
    return ""


def add_levels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = out["ts"].dt.date
    out["session"] = out["ts"].map(session_name)
    asian = out[(out["ts"].dt.hour >= 0) & (out["ts"].dt.hour < 7)]
    asian_ranges = asian.groupby("date").agg(asian_high=("high", "max"), asian_low=("low", "min"))
    out = out.join(asian_ranges, on="date")
    daily = out.groupby("date").agg(day_high=("high", "max"), day_low=("low", "min"))
    daily["pdh"] = daily["day_high"].shift(1)
    daily["pdl"] = daily["day_low"].shift(1)
    out = out.join(daily[["pdh", "pdl"]], on="date")
    ranges = out["high"] - out["low"]
    out["range_med_96"] = ranges.rolling(96, min_periods=20).median()
    out["ema50"] = out["close"].ewm(span=50, adjust=False).mean()
    out["ema200"] = out["close"].ewm(span=200, adjust=False).mean()
    return out


def detect_fvg_at(df: pd.DataFrame, i: int, direction: str, spec: AssetSpec, cfg: Config) -> dict | None:
    if i < 2:
        return None
    c1 = df.iloc[i - 2]
    c2 = df.iloc[i - 1]
    c3 = df.iloc[i]
    gap = 0.0
    top = bottom = ce = np.nan
    if direction == "long" and float(c3["low"]) > float(c1["high"]):
        bottom = float(c1["high"])
        top = float(c3["low"])
        gap = top - bottom
    elif direction == "short" and float(c3["high"]) < float(c1["low"]):
        top = float(c1["low"])
        bottom = float(c3["high"])
        gap = top - bottom
    else:
        return None
    gap_pips = gap / spec.pip
    if gap_pips < cfg.min_gap_pips:
        return None
    med = float(df["range_med_96"].iloc[i])
    c2_range = float(c2["high"] - c2["low"])
    if not np.isfinite(med) or med <= 0 or c2_range < cfg.min_disp_ratio * med:
        return None
    ce = (top + bottom) / 2.0
    return {"fvg_top": top, "fvg_bottom": bottom, "fvg_ce": ce, "gap_pips": gap_pips}


def first_hit_costed(
    path: pd.DataFrame,
    direction: str,
    signal_entry: float,
    stop: float,
    rr: float,
    spec: AssetSpec,
    costs: CostSpec,
) -> tuple[float, str, pd.Timestamp | None]:
    sign = 1 if direction == "long" else -1
    entry_fill = signal_entry + sign * costs.entry_spread_pips * spec.pip
    risk = abs(entry_fill - stop)
    if not np.isfinite(risk) or risk <= 0:
        return np.nan, "bad_risk", None
    risk_pips = risk / spec.pip
    commission_r = costs.round_trip_commission_per_lot / max(risk_pips * spec.pip_value_per_lot, 1e-9)
    if direction == "long":
        tp = entry_fill + rr * risk
        for _, bar in path.iterrows():
            sl_hit = float(bar["low"]) <= stop
            tp_hit = float(bar["high"]) >= tp
            if sl_hit:
                exit_fill = stop - (costs.sl_exit_spread_pips + costs.slippage_pips) * spec.pip
                return (exit_fill - entry_fill) / risk - commission_r, "sl", bar["ts"]
            if tp_hit:
                exit_fill = tp - costs.tp_exit_spread_pips * spec.pip
                return (exit_fill - entry_fill) / risk - commission_r, "tp", bar["ts"]
        final_fill = float(path["close"].iloc[-1]) - costs.tp_exit_spread_pips * spec.pip
        return (final_fill - entry_fill) / risk - commission_r, "time", path["ts"].iloc[-1]
    tp = entry_fill - rr * risk
    for _, bar in path.iterrows():
        sl_hit = float(bar["high"]) >= stop
        tp_hit = float(bar["low"]) <= tp
        if sl_hit:
            exit_fill = stop + (costs.sl_exit_spread_pips + costs.slippage_pips) * spec.pip
            return (entry_fill - exit_fill) / risk - commission_r, "sl", bar["ts"]
        if tp_hit:
            exit_fill = tp + costs.tp_exit_spread_pips * spec.pip
            return (entry_fill - exit_fill) / risk - commission_r, "tp", bar["ts"]
    final_fill = float(path["close"].iloc[-1]) + costs.tp_exit_spread_pips * spec.pip
    return (entry_fill - final_fill) / risk - commission_r, "time", path["ts"].iloc[-1]


def find_entry(
    df: pd.DataFrame,
    fvg_i: int,
    direction: str,
    fvg: dict,
    sweep_extreme: float,
    cfg: Config,
    spec: AssetSpec,
) -> dict | None:
    stop = sweep_extreme - spec.buffer if direction == "long" else sweep_extreme + spec.buffer
    entry = float(fvg["fvg_ce"])
    stop_pips = abs(entry - stop) / spec.pip
    if stop_pips < cfg.min_stop_pips:
        return None
    end = min(fvg_i + cfg.retest_bars + 1, len(df) - cfg.hold_bars - 1)
    for j in range(fvg_i + 1, end):
        bar = df.iloc[j]
        touched = float(bar["low"]) <= entry if direction == "long" else float(bar["high"]) >= entry
        if not touched:
            continue
        path = df.iloc[j + 1 : j + cfg.hold_bars + 1]
        if path.empty:
            return None
        trade_r, reason, exit_ts = first_hit_costed(path, direction, entry, stop, cfg.rr, spec, CostSpec())
        return {
            "entry_i": j,
            "entry_ts": bar["ts"],
            "entry": entry,
            "stop": stop,
            "stop_pips": stop_pips,
            "trade_r": trade_r,
            "exit_reason": reason,
            "exit_ts": exit_ts,
        }
    return None


def detect_symbol(symbol: str, days: int, configs: list[Config]) -> pd.DataFrame:
    spec = spec_for(symbol)
    if spec.asset_type != "forex":
        return pd.DataFrame()
    df = load_data(symbol, "5", days=days, asset_type="forex")
    if df.empty:
        return pd.DataFrame()
    df = add_levels(df)
    rows = []
    max_forward = max(c.fvg_max_bars + c.retest_bars + c.hold_bars for c in configs)
    used: set[tuple] = set()
    for i in range(220, len(df) - max_forward - 1):
        bar = df.iloc[i]
        if not bar["session"]:
            continue
        levels = [
            ("asian_high", bar["asian_high"], "short", float(bar["high"])),
            ("pdh", bar["pdh"], "short", float(bar["high"])),
            ("asian_low", bar["asian_low"], "long", float(bar["low"])),
            ("pdl", bar["pdl"], "long", float(bar["low"])),
        ]
        for level_name, level, direction, sweep_extreme in levels:
            if not np.isfinite(level):
                continue
            if direction == "short":
                swept = float(bar["high"]) > float(level) and float(bar["close"]) < float(level)
            else:
                swept = float(bar["low"]) < float(level) and float(bar["close"]) > float(level)
            if not swept:
                continue
            for cfg in configs:
                if cfg.session != "all" and cfg.session != bar["session"]:
                    continue
                key = (symbol, str(bar["date"]), level_name, direction, cfg.id)
                if key in used:
                    continue
                for k in range(i + 1, min(i + cfg.fvg_max_bars + 1, len(df) - cfg.hold_bars - 1)):
                    fvg = detect_fvg_at(df, k, direction, spec, cfg)
                    if not fvg:
                        continue
                    entry = find_entry(df, k, direction, fvg, sweep_extreme, cfg, spec)
                    if not entry:
                        continue
                    used.add(key)
                    rows.append(
                        {
                            "symbol": symbol,
                            "ts": entry["entry_ts"],
                            "date": str(bar["date"]),
                            "session": bar["session"],
                            "level": level_name,
                            "direction": direction,
                            "rr_target": cfg.rr,
                            "rule_id": f"{symbol}|{level_name}|{direction}|{cfg.id}",
                            "sweep_ts": bar["ts"],
                            "sweep_level": float(level),
                            "sweep_extreme": sweep_extreme,
                            "fvg_ts": df.iloc[k]["ts"],
                            **fvg,
                            **entry,
                            "ema50_gt_ema200": int(float(bar["ema50"]) > float(bar["ema200"])),
                        }
                    )
                    break
    return pd.DataFrame(rows)


def simulate(trades: pd.DataFrame, risk_pct: float, max_trades_per_day: int, daily_lockout_pct: float) -> dict:
    if trades.empty:
        return {
            "n": 0, "return_pct": 0.0, "max_dd_pct": 0.0, "max_daily_loss_pct": 0.0,
            "win_rate_pct": 0.0, "avg_r": 0.0, "median_r": 0.0,
        }
    equity = ACCOUNT_SIZE
    peak = equity
    wins = 0
    max_dd = 0.0
    day_start: dict[str, float] = {}
    day_pnl: dict[str, float] = {}
    day_count: dict[str, int] = {}
    r_taken = []
    for _, row in trades.sort_values("ts").iterrows():
        day = str(pd.Timestamp(row["ts"]).date())
        day_start.setdefault(day, equity)
        day_count.setdefault(day, 0)
        if day_count[day] >= max_trades_per_day:
            continue
        day_loss = max(0.0, -day_pnl.get(day, 0.0) / day_start[day] * 100.0)
        if daily_lockout_pct > 0 and day_loss >= daily_lockout_pct:
            continue
        r = float(row["trade_r"])
        if not np.isfinite(r):
            continue
        pnl = ACCOUNT_SIZE * risk_pct * r
        equity += pnl
        day_pnl[day] = day_pnl.get(day, 0.0) + pnl
        day_count[day] += 1
        wins += int(pnl > 0)
        r_taken.append(r)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    max_daily_loss = 0.0
    for day, pnl in day_pnl.items():
        max_daily_loss = max(max_daily_loss, -pnl / day_start[day] * 100.0)
    return {
        "n": len(r_taken),
        "return_pct": (equity - ACCOUNT_SIZE) / ACCOUNT_SIZE * 100.0,
        "max_dd_pct": max_dd,
        "max_daily_loss_pct": max_daily_loss,
        "win_rate_pct": wins / max(len(r_taken), 1) * 100.0,
        "avg_r": float(np.mean(r_taken)) if r_taken else 0.0,
        "median_r": float(np.median(r_taken)) if r_taken else 0.0,
    }


def summarize(events: pd.DataFrame, risk_pct: float, max_trades_per_day: int, daily_lockout_pct: float) -> pd.DataFrame:
    rows = []
    if events.empty:
        return pd.DataFrame()
    for rule_id, group in events.groupby("rule_id"):
        metrics = simulate(group, risk_pct, max_trades_per_day, daily_lockout_pct)
        rows.append(
            {
                "rule_id": rule_id,
                "symbol": group["symbol"].iloc[0],
                "level": group["level"].iloc[0],
                "direction": group["direction"].iloc[0],
                "session": group["session"].mode().iloc[0],
                "rr_target": group["rr_target"].iloc[0],
                **metrics,
            }
        )
    return pd.DataFrame(rows).sort_values(["return_pct", "max_dd_pct"], ascending=[False, True])


def rolling_windows(
    events: pd.DataFrame,
    risk_pct: float,
    window_days: int,
    max_trades_per_day: int,
    daily_lockout_pct: float,
) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    events = events.sort_values("ts").copy()
    start = events["ts"].min().normalize()
    end = events["ts"].max().normalize()
    rows = []
    w = 0
    cur = start
    while cur + pd.Timedelta(days=window_days) <= end:
        w += 1
        nxt = cur + pd.Timedelta(days=window_days)
        sub = events[(events["ts"] >= cur) & (events["ts"] < nxt)].copy()
        metrics = simulate(sub, risk_pct, max_trades_per_day, daily_lockout_pct)
        rows.append({"window": w, "start": cur, "end": nxt, **metrics})
        cur += pd.Timedelta(days=window_days)
    return pd.DataFrame(rows)


def config_grid(mode: str) -> list[Config]:
    configs = []
    if mode == "wide":
        fvg_bars = [3, 6, 9]
        retests = [6, 12, 24]
        gaps = [0.5, 1.0, 1.5]
        disps = [1.2, 1.5, 2.0]
    else:
        fvg_bars = [3, 6]
        retests = [12, 24]
        gaps = [1.0]
        disps = [1.5]
    for session in ["london", "ny"]:
        for rr in [1.0, 1.5, 2.0]:
            for fvg_max in fvg_bars:
                for retest in retests:
                    for gap in gaps:
                        for disp in disps:
                            configs.append(
                                Config(
                                    rr=rr,
                                    fvg_max_bars=fvg_max,
                                    retest_bars=retest,
                                    hold_bars=36,
                                    min_gap_pips=gap,
                                    min_disp_ratio=disp,
                                    min_stop_pips=5.0,
                                    session=session,
                                )
                            )
    return configs


def main() -> None:
    parser = argparse.ArgumentParser(description="5m FX liquidity sweep + FVG retest lab.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_FX))
    parser.add_argument("--days", type=int, default=490)
    parser.add_argument("--tag", default="liquidity_fvg_v1")
    parser.add_argument("--risk-pct", type=float, default=0.5)
    parser.add_argument("--max-trades-per-day", type=int, default=3)
    parser.add_argument("--daily-lockout-pct", type=float, default=1.0)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--grid", choices=["fast", "wide"], default="fast")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    configs = config_grid(args.grid)
    print(f"Config count: {len(configs)}")
    frames = []
    for symbol in symbols:
        events = detect_symbol(symbol, args.days, configs)
        print(f"{symbol}: {len(events)} events")
        if not events.empty:
            frames.append(events)
    events = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not events.empty:
        events["ts"] = pd.to_datetime(events["ts"], utc=True)

    events_path = OUT / f"{args.tag}_events.csv"
    summary_path = OUT / f"{args.tag}_summary.csv"
    rolling_path = OUT / f"{args.tag}_rolling30.csv"
    events.to_csv(events_path, index=False)
    summary = summarize(events, args.risk_pct / 100.0, args.max_trades_per_day, args.daily_lockout_pct)
    summary.to_csv(summary_path, index=False)
    rolling = rolling_windows(events, args.risk_pct / 100.0, 30, args.max_trades_per_day, args.daily_lockout_pct)
    rolling.to_csv(rolling_path, index=False)
    print(f"Saved {events_path} rows={len(events)}")
    print(f"Saved {summary_path} rows={len(summary)}")
    print(f"Saved {rolling_path} rows={len(rolling)}")
    if not summary.empty:
        cols = ["rule_id", "n", "return_pct", "max_dd_pct", "win_rate_pct", "avg_r", "median_r"]
        print("\nTOP RULES")
        print(summary[cols].head(args.top).to_string(index=False))
    if not rolling.empty:
        print("\nALL-EVENT 30D WINDOWS")
        print(rolling[["window", "start", "end", "n", "return_pct", "max_dd_pct", "win_rate_pct", "avg_r"]].to_string(index=False))


if __name__ == "__main__":
    main()
