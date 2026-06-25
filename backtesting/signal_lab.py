#!/usr/bin/env python3
"""Signal-level research lab.

This is not a strategy backtest. It tests whether raw setup events have a
measurable path edge before we waste time engineering entries/exits.

Default assets:
  EURUSD, GBPUSD, GBPJPY, AUDJPY, USDCAD, XAUUSD

Signals:
  - Asian range sweep during London/NY, reversal and continuation variants
  - Prior-day high/low sweep during London/NY, reversal and continuation variants

Outputs:
  - backtesting/results/signal_lab_<tag>_events.csv
  - backtesting/results/signal_lab_<tag>_summary.csv
  - backtesting/results/signal_lab_<tag>_learning_curve.csv
  - backtesting/results/signal_lab_<tag>_account_curve.csv
  - backtesting/results/signal_lab_<tag>_filter_account_curve.csv
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

from backtesting.engine.data import load_data

OUT = ROOT / "backtesting" / "results"
OUT.mkdir(parents=True, exist_ok=True)

DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD", "GBPJPY", "AUDJPY", "USDCAD", "XAUUSD"]
FORWARD_BARS = [6, 12, 24, 48]  # 5m bars = 30m, 1h, 2h, 4h
ACCOUNT_SIZE = 25_000.0
RISK_PCT = 0.005
ACCOUNT_KEYS = ["symbol", "session", "signal", "variant", "direction", "htf"]


@dataclass(frozen=True)
class AssetSpec:
    symbol: str
    asset_type: str
    pip: float
    buffer: float
    pip_value_per_lot: float = 10.0


@dataclass(frozen=True)
class CostSpec:
    entry_spread_pips: float = 2.0
    tp_exit_spread_pips: float = 1.0
    sl_exit_spread_pips: float = 1.0
    slippage_pips: float = 0.5
    round_trip_commission_per_lot: float = 1.50


def spec_for(symbol: str) -> AssetSpec:
    if symbol == "XAUUSD":
        return AssetSpec(symbol, "commodity", 0.1, 1.0)
    if symbol.endswith("JPY"):
        return AssetSpec(symbol, "forex", 0.01, 0.03, 9.0)
    return AssetSpec(symbol, "forex", 0.0001, 0.0003)


def session_name(ts: pd.Timestamp) -> str:
    h = ts.hour
    if 7 <= h < 10:
        return "london"
    if 13 <= h < 16:
        return "ny"
    return ""


def htf_state(df: pd.DataFrame) -> np.ndarray:
    df4 = df.set_index("ts").resample("4h").agg({"close": "last"}).dropna()
    df4["ema20"] = df4["close"].ewm(span=20, adjust=False).mean()
    df4["htf"] = np.where(df4["close"] > df4["ema20"], "bullish", "bearish")
    htf = df4[["htf"]].copy()
    htf["available_ts"] = htf.index + pd.Timedelta(hours=4)
    merged = pd.merge_asof(
        df[["ts"]].sort_values("ts"),
        htf[["available_ts", "htf"]].sort_values("available_ts"),
        left_on="ts",
        right_on="available_ts",
        direction="backward",
    )
    return merged["htf"].fillna("neutral").to_numpy(dtype=object)


def add_ranges(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = df["ts"].dt.date
    df["session"] = df["ts"].map(session_name)
    df["htf"] = htf_state(df)
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ret_15_prev"] = df["close"].pct_change(15)
    df["range_15_prev"] = (df["high"].rolling(15).max() - df["low"].rolling(15).min()) / df["close"]

    asian = df[(df["ts"].dt.hour >= 0) & (df["ts"].dt.hour < 7)]
    asian_ranges = asian.groupby("date").agg(asian_high=("high", "max"), asian_low=("low", "min"))
    df = df.join(asian_ranges, on="date")

    daily = df.groupby("date").agg(day_high=("high", "max"), day_low=("low", "min"))
    daily["pdh"] = daily["day_high"].shift(1)
    daily["pdl"] = daily["day_low"].shift(1)
    df = df.join(daily[["pdh", "pdl"]], on="date")
    return df


def direction_accuracy(df: pd.DataFrame, i: int, direction: str, bars: int = 15) -> tuple[int, float]:
    end = min(i + bars, len(df) - 1)
    if end <= i:
        return 0, 0.0
    entry = float(df["close"].iloc[i])
    future = float(df["close"].iloc[end])
    sign = 1 if direction == "long" else -1
    move = sign * (future - entry)
    return int(move > 0), move / entry


def pre_context(df: pd.DataFrame, i: int, direction: str) -> dict:
    start = max(0, i - 15)
    prev = df.iloc[start:i]
    entry = float(df["close"].iloc[i])
    sign = 1 if direction == "long" else -1
    if prev.empty:
        return {
            "prev_15_aligned": 0,
            "prev_15_move_pct": 0.0,
            "prev_15_range_pct": 0.0,
            "ema_aligned": 0,
        }
    prev_move = sign * (entry - float(prev["close"].iloc[0])) / float(prev["close"].iloc[0])
    prev_range = (float(prev["high"].max()) - float(prev["low"].min())) / entry
    ema_aligned = int((entry > float(df["ema20"].iloc[i]) > float(df["ema50"].iloc[i])) if direction == "long" else (entry < float(df["ema20"].iloc[i]) < float(df["ema50"].iloc[i])))
    return {
        "prev_15_aligned": int(prev_move > 0),
        "prev_15_move_pct": prev_move * 100.0,
        "prev_15_range_pct": prev_range * 100.0,
        "ema_aligned": ema_aligned,
    }


def forward_path(df: pd.DataFrame, i: int, direction: str, entry: float, stop: float, spec: AssetSpec) -> dict:
    risk = abs(entry - stop)
    if not np.isfinite(risk) or risk <= 0:
        return {}
    sign = 1 if direction == "long" else -1
    row = {"risk": risk}
    for bars in FORWARD_BARS:
        end = min(i + bars, len(df) - 1)
        path = df.iloc[i + 1 : end + 1]
        if path.empty:
            continue
        final = float(path["close"].iloc[-1])
        if direction == "long":
            mfe = (float(path["high"].max()) - entry) / risk
            mae = (entry - float(path["low"].min())) / risk
        else:
            mfe = (entry - float(path["low"].min())) / risk
            mae = (float(path["high"].max()) - entry) / risk
        final_r = sign * (final - entry) / risk
        row[f"r_{bars}"] = final_r
        row[f"mfe_{bars}"] = mfe
        row[f"mae_{bars}"] = mae
        for target in [1, 2, 3]:
            row[f"hit_{target}r_{bars}"] = int(mfe >= target)
        row[f"hit_sl_{bars}"] = int(mae >= 1)
        for target in [1, 2, 3]:
            row[f"tp{target}_sl1_first_{bars}"] = first_hit_outcome(path, direction, entry, stop, target)
            row[f"tp{target}_sl1_costed_{bars}"] = first_hit_outcome_costed(
                path,
                direction,
                entry,
                stop,
                target,
                spec,
                CostSpec(),
            )
    return row


def first_hit_outcome(path: pd.DataFrame, direction: str, entry: float, stop: float, target: int) -> float:
    """Conservative first-hit R outcome. Same-bar TP/SL ambiguity is counted as -1R."""
    risk = abs(entry - stop)
    if not np.isfinite(risk) or risk <= 0:
        return np.nan
    highs = path["high"].to_numpy(dtype=float)
    lows = path["low"].to_numpy(dtype=float)
    if direction == "long":
        tp = entry + target * risk
        for high, low in zip(highs, lows):
            sl_hit = low <= stop
            tp_hit = high >= tp
            if sl_hit:
                return -1.0
            if tp_hit:
                return float(target)
    else:
        tp = entry - target * risk
        for high, low in zip(highs, lows):
            sl_hit = high >= stop
            tp_hit = low <= tp
            if sl_hit:
                return -1.0
            if tp_hit:
                return float(target)
    return 0.0


def first_hit_outcome_costed(
    path: pd.DataFrame,
    direction: str,
    signal_entry: float,
    stop: float,
    target: int,
    spec: AssetSpec,
    costs: CostSpec,
) -> float:
    """First-hit R including deterministic adverse spread, SL slippage, and commission."""
    sign = 1 if direction == "long" else -1
    entry_fill = signal_entry + sign * costs.entry_spread_pips * spec.pip
    risk = abs(entry_fill - stop)
    if not np.isfinite(risk) or risk <= 0:
        return np.nan
    risk_pips = risk / spec.pip
    commission_r = costs.round_trip_commission_per_lot / max(risk_pips * spec.pip_value_per_lot, 1e-9)
    highs = path["high"].to_numpy(dtype=float)
    lows = path["low"].to_numpy(dtype=float)

    if direction == "long":
        tp = entry_fill + target * risk
        for high, low in zip(highs, lows):
            sl_hit = low <= stop
            tp_hit = high >= tp
            if sl_hit:
                exit_fill = stop - (costs.sl_exit_spread_pips + costs.slippage_pips) * spec.pip
                return (exit_fill - entry_fill) / risk - commission_r
            if tp_hit:
                exit_fill = tp - costs.tp_exit_spread_pips * spec.pip
                return (exit_fill - entry_fill) / risk - commission_r
        final_fill = float(path["close"].iloc[-1]) - costs.tp_exit_spread_pips * spec.pip
        return (final_fill - entry_fill) / risk - commission_r

    tp = entry_fill - target * risk
    for high, low in zip(highs, lows):
        sl_hit = high >= stop
        tp_hit = low <= tp
        if sl_hit:
            exit_fill = stop + (costs.sl_exit_spread_pips + costs.slippage_pips) * spec.pip
            return (entry_fill - exit_fill) / risk - commission_r
        if tp_hit:
            exit_fill = tp + costs.tp_exit_spread_pips * spec.pip
            return (entry_fill - exit_fill) / risk - commission_r
    final_fill = float(path["close"].iloc[-1]) + costs.tp_exit_spread_pips * spec.pip
    return (entry_fill - final_fill) / risk - commission_r


def add_event(rows: list[dict], df: pd.DataFrame, i: int, spec: AssetSpec, signal: str, level: float, swept_high: bool) -> None:
    bar = df.iloc[i]
    sess = bar["session"]
    if not sess:
        return
    entry = float(bar["close"])

    variants = []
    if swept_high:
        variants.append(("reversal", "short", float(bar["high"]) + spec.buffer))
        variants.append(("continuation", "long", float(bar["low"]) - spec.buffer))
    else:
        variants.append(("reversal", "long", float(bar["low"]) - spec.buffer))
        variants.append(("continuation", "short", float(bar["high"]) + spec.buffer))

    extension = (float(bar["high"]) - level) if swept_high else (level - float(bar["low"]))
    for variant, direction, stop in variants:
        path = forward_path(df, i, direction, entry, stop, spec)
        if not path:
            continue
        dir_ok, dir_move = direction_accuracy(df, i, direction, bars=15)
        context = pre_context(df, i, direction)
        rows.append(
            {
                "symbol": spec.symbol,
                "asset_type": spec.asset_type,
                "ts": bar["ts"],
                "date": str(bar["date"]),
                "session": sess,
                "signal": signal,
                "variant": variant,
                "direction": direction,
                "htf": bar["htf"],
                "level": level,
                "entry": entry,
                "stop": stop,
                "extension": extension,
                "extension_pips": extension / spec.pip,
                "direction_ok_15": dir_ok,
                "direction_move_15_pct": dir_move * 100.0,
                **context,
                **path,
            }
        )


def detect_events(symbol: str, days: int) -> pd.DataFrame:
    spec = spec_for(symbol)
    df = load_data(symbol, "5", days=days, asset_type=spec.asset_type)
    if df.empty:
        return pd.DataFrame()
    df = add_ranges(df)

    rows: list[dict] = []
    seen: set[tuple] = set()
    for i in range(1, len(df) - max(FORWARD_BARS) - 1):
        bar = df.iloc[i]
        if not bar["session"]:
            continue
        checks = [
            ("asian_high_sweep", bar["asian_high"], True),
            ("asian_low_sweep", bar["asian_low"], False),
            ("pdh_sweep", bar["pdh"], True),
            ("pdl_sweep", bar["pdl"], False),
        ]
        for signal, level, swept_high in checks:
            if not np.isfinite(level):
                continue
            if swept_high:
                swept = float(bar["high"]) > level and float(bar["close"]) < level
            else:
                swept = float(bar["low"]) < level and float(bar["close"]) > level
            if not swept:
                continue
            key = (bar["date"], signal)
            if key in seen:
                continue
            seen.add(key)
            add_event(rows, df, i, spec, signal, float(level), swept_high)
    return pd.DataFrame(rows)


def summarize(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    group_cols = ["symbol", "session", "signal", "variant", "direction", "htf"]

    def agg(g: pd.DataFrame) -> pd.Series:
        r_col = "r_24"
        mfe_col = "mfe_24"
        mae_col = "mae_24"
        r = g[r_col].dropna()
        t_stat = float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))) if len(r) > 1 and r.std(ddof=1) > 0 else 0.0
        return pd.Series(
            {
                "n": len(g),
                "duration_days": int((pd.to_datetime(g["ts"]).max() - pd.to_datetime(g["ts"]).min()).days) + 1,
                "avg_r_24": float(g[r_col].mean()),
                "med_r_24": float(g[r_col].median()),
                "max_r_24": float(g[r_col].max()),
                "min_r_24": float(g[r_col].min()),
                "avg_mfe_24": float(g[mfe_col].mean()),
                "avg_mae_24": float(g[mae_col].mean()),
                "hit_1r_24": float(g["hit_1r_24"].mean() * 100),
                "hit_2r_24": float(g["hit_2r_24"].mean() * 100),
                "hit_3r_24": float(g["hit_3r_24"].mean() * 100),
                "sl_hit_24": float(g["hit_sl_24"].mean() * 100),
                "tp1_wr_24": float((g["tp1_sl1_first_24"] > 0).mean() * 100),
                "tp2_wr_24": float((g["tp2_sl1_first_24"] > 0).mean() * 100),
                "tp3_wr_24": float((g["tp3_sl1_first_24"] > 0).mean() * 100),
                "tp1_avg_r_24": float(g["tp1_sl1_first_24"].mean()),
                "tp2_avg_r_24": float(g["tp2_sl1_first_24"].mean()),
                "tp3_avg_r_24": float(g["tp3_sl1_first_24"].mean()),
                "tp1_costed_wr_24": float((g["tp1_sl1_costed_24"] > 0).mean() * 100),
                "tp2_costed_wr_24": float((g["tp2_sl1_costed_24"] > 0).mean() * 100),
                "tp3_costed_wr_24": float((g["tp3_sl1_costed_24"] > 0).mean() * 100),
                "tp1_costed_avg_r_24": float(g["tp1_sl1_costed_24"].mean()),
                "tp2_costed_avg_r_24": float(g["tp2_sl1_costed_24"].mean()),
                "tp3_costed_avg_r_24": float(g["tp3_sl1_costed_24"].mean()),
                "positive_24": float((g[r_col] > 0).mean() * 100),
                "direction_accuracy_15": float(g["direction_ok_15"].mean() * 100),
                "prev_15_aligned": float(g["prev_15_aligned"].mean() * 100),
                "ema_aligned": float(g["ema_aligned"].mean() * 100),
                "t_stat_24": t_stat,
            }
        )

    out = events.groupby(group_cols).apply(agg, include_groups=False).reset_index()
    out["score"] = (
        out["avg_r_24"] * 20
        + out["avg_mfe_24"] * 8
        + out["hit_2r_24"] * 0.15
        + out["positive_24"] * 0.08
        - out["sl_hit_24"] * 0.12
    )
    return out.sort_values(["score", "n"], ascending=[False, False])


def r_column_for_exit_model(exit_model: str) -> str:
    if exit_model == "close24":
        return "r_24"
    if exit_model in {"tp1_sl1_24", "tp2_sl1_24", "tp3_sl1_24"}:
        return exit_model.replace("_24", "_first_24")
    if exit_model in {"tp1_costed_24", "tp2_costed_24", "tp3_costed_24"}:
        return exit_model.replace("_costed_24", "_sl1_costed_24")
    raise ValueError(f"Unknown exit model: {exit_model}")


def account_curve(
    events: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    exit_model: str,
    daily_lockout_pct: float,
) -> pd.DataFrame:
    if events.empty or summary.empty:
        return pd.DataFrame()
    keys = ACCOUNT_KEYS
    r_col = r_column_for_exit_model(exit_model)
    if r_col not in events.columns:
        return pd.DataFrame()
    rows = []
    keyed_summary = summary.set_index(keys)
    for key, g in events.sort_values("ts").groupby(keys):
        equity = ACCOUNT_SIZE
        peak = equity
        max_dd = 0.0
        max_trade_ret = -999.0
        day_start_equity: dict[str, float] = {}
        day_pnl: dict[str, float] = {}
        wins = 0
        losses = 0
        skipped_daily_lockout = 0
        pnls = []
        for _, row in g.iterrows():
            day = str(pd.Timestamp(row["ts"]).date())
            day_start_equity.setdefault(day, equity)
            day_base = day_start_equity[day]
            day_loss_pct = max(0.0, -day_pnl.get(day, 0.0) / day_base * 100.0) if day_base else 0.0
            if daily_lockout_pct > 0 and day_loss_pct >= daily_lockout_pct:
                skipped_daily_lockout += 1
                continue
            r = float(row[r_col])
            if not np.isfinite(r):
                continue
            pnl = ACCOUNT_SIZE * RISK_PCT * r
            equity += pnl
            day_pnl[day] = day_pnl.get(day, 0.0) + pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
            max_trade_ret = max(max_trade_ret, pnl / ACCOUNT_SIZE * 100.0)
            pnls.append(pnl)
            if pnl > 0:
                wins += 1
            else:
                losses += 1
        max_daily_loss = 0.0
        max_daily_gain = 0.0
        for day, pnl in day_pnl.items():
            base = day_start_equity.get(day, ACCOUNT_SIZE)
            day_ret = pnl / base * 100.0 if base else 0.0
            max_daily_loss = max(max_daily_loss, -day_ret)
            max_daily_gain = max(max_daily_gain, day_ret)
        start = pd.to_datetime(g["ts"]).min()
        end = pd.to_datetime(g["ts"]).max()
        s = keyed_summary.loc[key]
        rows.append(
            {
                **dict(zip(keys, key)),
                "exit_model": exit_model,
                "timeframe": "5m",
                "account": ACCOUNT_SIZE,
                "risk_pct": RISK_PCT * 100.0,
                "daily_lockout_pct": daily_lockout_pct,
                "duration_days": int((end - start).days) + 1,
                "n": int(len(g) - skipped_daily_lockout),
                "signals": int(len(g)),
                "skipped_daily_lockout": int(skipped_daily_lockout),
                "return_pct": float((equity - ACCOUNT_SIZE) / ACCOUNT_SIZE * 100.0),
                "max_dd_pct": float(max_dd),
                "max_daily_loss_pct": float(max_daily_loss),
                "max_daily_gain_pct": float(max_daily_gain),
                "max_trade_return_pct": float(max_trade_ret),
                "win_rate_pct": float(wins / max(wins + losses, 1) * 100.0),
                "avg_r": float(g[r_col].replace([np.inf, -np.inf], np.nan).dropna().mean()),
                "median_r": float(g[r_col].replace([np.inf, -np.inf], np.nan).dropna().median()),
                "max_r": float(g[r_col].replace([np.inf, -np.inf], np.nan).dropna().max()),
                "min_r": float(g[r_col].replace([np.inf, -np.inf], np.nan).dropna().min()),
                "avg_mfe_r": float(g["mfe_24"].mean()),
                "avg_mae_r": float(g["mae_24"].mean()),
                "direction_accuracy_15": float(s["direction_accuracy_15"]),
                "prev_15_aligned": float(s["prev_15_aligned"]),
                "ema_aligned": float(s["ema_aligned"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["return_pct", "max_dd_pct"], ascending=[False, True])


def filter_profiles(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Live-available filters only. No future direction/hit columns allowed."""
    if events.empty:
        return {}
    profiles = {
        "all": events,
        "prev15_aligned": events[events["prev_15_aligned"] == 1],
        "ema_aligned": events[events["ema_aligned"] == 1],
        "prev15_and_ema": events[(events["prev_15_aligned"] == 1) & (events["ema_aligned"] == 1)],
        "min_extension_3pip": events[events["extension_pips"] >= 3],
        "min_extension_5pip": events[events["extension_pips"] >= 5],
        "prev15_and_ext3": events[(events["prev_15_aligned"] == 1) & (events["extension_pips"] >= 3)],
    }
    return {name: df.copy() for name, df in profiles.items() if len(df) > 0}


def filtered_account_curves(events: pd.DataFrame, *, exit_models: list[str], daily_lockout_pct: float) -> pd.DataFrame:
    rows = []
    for profile, sub in filter_profiles(events).items():
        summary = summarize(sub)
        for exit_model in exit_models:
            acct = account_curve(sub, summary, exit_model=exit_model, daily_lockout_pct=daily_lockout_pct)
            if acct.empty:
                continue
            acct.insert(0, "filter_profile", profile)
            rows.append(acct)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True).sort_values(
        ["return_pct", "max_dd_pct", "win_rate_pct"],
        ascending=[False, True, False],
    )


def learning_curve(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows = []
    keys = ACCOUNT_KEYS
    for key, g in events.sort_values("ts").groupby(keys):
        for n in [25, 50, 100, 200, 500, 1000]:
            sub = g.head(n)
            if len(sub) < min(n, 25):
                continue
            rows.append(
                {
                    **dict(zip(keys, key)),
                    "n": len(sub),
                    "avg_r_24": float(sub["r_24"].mean()),
                    "avg_mfe_24": float(sub["mfe_24"].mean()),
                    "hit_2r_24": float(sub["hit_2r_24"].mean() * 100),
                    "sl_hit_24": float(sub["hit_sl_24"].mean() * 100),
                    "positive_24": float((sub["r_24"] > 0).mean() * 100),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Signal-level trading research lab.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--tag", default="")
    parser.add_argument("--min-n-print", type=int, default=0)
    parser.add_argument("--daily-lockout-pct", type=float, default=3.0)
    parser.add_argument("--exit-models", default="close24,tp1_sl1_24,tp2_sl1_24,tp3_sl1_24")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    exit_models = [m.strip() for m in args.exit_models.split(",") if m.strip()]
    min_n_print = args.min_n_print if args.min_n_print > 0 else (5 if args.days <= 60 else 20)
    tag = args.tag.strip() or f"{args.days}d"
    frames = []
    for symbol in symbols:
        events = detect_events(symbol, args.days)
        print(f"{symbol}: {len(events)} signal variants")
        if not events.empty:
            frames.append(events)
    all_events = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    summary = summarize(all_events)
    curve = learning_curve(all_events)
    account_frames = [
        account_curve(all_events, summary, exit_model=exit_model, daily_lockout_pct=args.daily_lockout_pct)
        for exit_model in exit_models
    ]
    account = pd.concat([df for df in account_frames if not df.empty], ignore_index=True) if account_frames else pd.DataFrame()
    if not account.empty:
        account = account.sort_values(["return_pct", "max_dd_pct", "win_rate_pct"], ascending=[False, True, False])
    filtered_account = filtered_account_curves(
        all_events,
        exit_models=exit_models,
        daily_lockout_pct=args.daily_lockout_pct,
    )

    events_path = OUT / f"signal_lab_{tag}_events.csv"
    summary_path = OUT / f"signal_lab_{tag}_summary.csv"
    curve_path = OUT / f"signal_lab_{tag}_learning_curve.csv"
    account_path = OUT / f"signal_lab_{tag}_account_curve.csv"
    filtered_account_path = OUT / f"signal_lab_{tag}_filter_account_curve.csv"
    outputs = [
        (all_events, events_path, OUT / "signal_lab_events.csv"),
        (summary, summary_path, OUT / "signal_lab_summary.csv"),
        (curve, curve_path, OUT / "signal_lab_learning_curve.csv"),
        (account, account_path, OUT / "signal_lab_account_curve.csv"),
        (filtered_account, filtered_account_path, OUT / "signal_lab_filter_account_curve.csv"),
    ]
    for df, tagged_path, latest_path in outputs:
        df.to_csv(tagged_path, index=False)
        df.to_csv(latest_path, index=False)

    print(f"\nSaved {events_path} rows={len(all_events)}")
    print(f"Saved {summary_path} rows={len(summary)}")
    print(f"Saved {curve_path} rows={len(curve)}")
    print(f"Saved {account_path} rows={len(account)}")
    print(f"Saved {filtered_account_path} rows={len(filtered_account)}")
    if not summary.empty:
        cols = [
            "symbol", "session", "signal", "variant", "direction", "htf", "n",
            "duration_days", "avg_r_24", "max_r_24", "avg_mfe_24", "avg_mae_24",
            "hit_2r_24", "sl_hit_24", "positive_24", "direction_accuracy_15",
            "t_stat_24", "score",
        ]
        print("\nTOP SIGNALS")
        printable = summary[summary["n"] >= min_n_print]
        print(printable[cols].head(args.top).to_string(index=False))
    if not account.empty:
        cols = [
            "symbol", "session", "signal", "variant", "direction", "htf", "exit_model",
            "timeframe", "duration_days", "n", "signals", "skipped_daily_lockout", "return_pct", "max_dd_pct",
            "max_daily_loss_pct", "max_trade_return_pct", "win_rate_pct", "avg_r", "max_r",
            "direction_accuracy_15",
        ]
        print("\nTOP 25K ACCOUNT CURVES")
        print(account[account["n"] >= min_n_print][cols].head(args.top).to_string(index=False))
    if not filtered_account.empty:
        cols = [
            "filter_profile", "symbol", "session", "signal", "variant", "direction", "htf", "exit_model",
            "duration_days", "n", "signals", "skipped_daily_lockout", "return_pct", "max_dd_pct", "max_daily_loss_pct",
            "win_rate_pct", "avg_r", "max_r", "direction_accuracy_15",
        ]
        print("\nTOP FILTERED 25K CURVES")
        print(filtered_account[filtered_account["n"] >= min_n_print][cols].head(args.top).to_string(index=False))


if __name__ == "__main__":
    main()
