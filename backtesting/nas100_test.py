#!/usr/bin/env python3
"""
NAS100 Backtest — Multi-Strategy, Multi-TF, Rolling Windows.

Loads USATECHIDXUSD data from data/market_data/index/NAS100/.

Strategies tested:
  - EMA Crossover (fast/slow)
  - RSI Mean Reversion
  - SMA Pullback (price → SMA bounce)
  - Breakout (N-bar range breakout)

Configs:
  - Entry TFs: 5m, 15m, 30m, 60m
  - Bias TFs:  60m, 240m (trend filter)
  - Exit:      fixed R:R (1.5, 2.0, 3.0), ATR trailing

Run:
  python backtesting/nas100_test.py                          # quick run
  python backtesting/nas100_test.py --sweep                  # full config sweep
  python backtesting/nas100_test.py --monthly                # rolling monthly
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────────
_SCRIPT = Path(__file__).parent
_ROOT   = _SCRIPT.parent
sys.path.insert(0, str(_ROOT))

DATA_DIR = _ROOT / "data" / "market_data" / "index" / "NAS100"
RNG = np.random.default_rng(42)

# ── Config ────────────────────────────────────────────────────────────────────

ENTRY_TFS = ["5", "15", "30", "60"]
BIAS_TFS = ["60", "240"]
RR_VALUES = [1.5, 2.0, 3.0]
STRATEGIES = ["ema_cross", "rsi_reversal", "sma_pullback", "breakout"]

@dataclass
class Config:
    name: str = "default"
    entry_tf: str = "15"
    bias_tf: str = "60"
    strategy: str = "ema_cross"
    rr: float = 2.0
    trail_atr: float = 2.0
    sl_atr: float = 1.5
    risk_pct: float = 0.01
    ema_fast: int = 9
    ema_slow: int = 21
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    sma_period: int = 50
    breakout_bars: int = 20

    def label(self) -> str:
        return f"{self.strategy}_e{self.entry_tf}_b{self.bias_tf}_rr{self.rr}"


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_nas100(tf: str, days: int = 30) -> pd.DataFrame:
    """Load NAS100 data for a given timeframe (minute value, e.g. '5', '15', '30', '60', '240', '1440')."""
    f = DATA_DIR / f"USATECHIDXUSD{tf}.csv"
    if not f.exists():
        print(f"  ⚠ Missing {f}")
        return pd.DataFrame()

    # Format: tab-separated, no header: ts(YYYY-MM-DD HH:MM) open high low close volume
    df = pd.read_csv(
        f, sep="\t", header=None,
        names=["ts", "open", "high", "low", "close", "volume"],
        parse_dates=["ts"],
    )
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.sort_values("ts").reset_index(drop=True)

    if days and len(df) > 0:
        cutoff = df["ts"].max() - pd.Timedelta(days=days)
        df = df[df["ts"] >= cutoff].reset_index(drop=True)

    # Drop rows with bad data
    df = df.dropna()
    return df


def resample_to_tf(df: pd.DataFrame, tf_minutes: str) -> pd.DataFrame:
    """Resample 1m data to higher timeframe. Only needed if source is 1m."""
    rule = f"{tf_minutes}min"
    df = df.set_index("ts").resample(rule).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna().reset_index()
    return df


# ── Indicators ────────────────────────────────────────────────────────────────

def add_ema(df: pd.DataFrame, period: int) -> pd.DataFrame:
    df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()
    return df


def add_sma(df: pd.DataFrame, period: int) -> pd.DataFrame:
    df[f"sma_{period}"] = df["close"].rolling(period).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period, min_periods=period).mean()
    avg_loss = loss.rolling(period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    df["rsi"] = df["rsi"].fillna(50)
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high, low, prev_close = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(period, min_periods=period).mean()
    df["atr"] = df["atr"].bfill().fillna(0)
    return df


# ── Entry Signals ─────────────────────────────────────────────────────────────

def detect_ema_cross(df: pd.DataFrame, cfg: Config) -> pd.Series:
    """1 = long signal, -1 = short signal, 0 = none. EMAs already added."""
    fast = f"ema_{cfg.ema_fast}"
    slow = f"ema_{cfg.ema_slow}"
    if fast not in df or slow not in df:
        return pd.Series(0, index=df.index)

    prev_fast = df[fast].shift(1)
    prev_slow = df[slow].shift(1)
    # Golden cross: fast crosses above slow
    long_cross = (prev_fast <= prev_slow) & (df[fast] > df[slow])
    # Death cross: fast crosses below slow
    short_cross = (prev_fast >= prev_slow) & (df[fast] < df[slow])

    signals = pd.Series(0, index=df.index)
    signals[long_cross] = 1
    signals[short_cross] = -1
    return signals


def detect_rsi_reversal(df: pd.DataFrame, cfg: Config) -> pd.Series:
    """Oversold bounce = long, overbought rejection = short. Only on RSI extremes."""
    if "rsi" not in df:
        return pd.Series(0, index=df.index)

    signals = pd.Series(0, index=df.index)
    # Oversold: RSI < threshold and now turning up
    oversold = (df["rsi"].shift(1) < cfg.rsi_oversold) & (df["rsi"] > cfg.rsi_oversold)
    overbought = (df["rsi"].shift(1) > cfg.rsi_overbought) & (df["rsi"] < cfg.rsi_overbought)
    signals[oversold] = 1
    signals[overbought] = -1
    return signals


def detect_sma_pullback(df: pd.DataFrame, cfg: Config) -> pd.Series:
    """Price pulls back to SMA(50) with rejection candle."""
    sma = f"sma_{cfg.sma_period}"
    if sma not in df:
        return pd.Series(0, index=df.index)

    signals = pd.Series(0, index=df.index)
    prev_close = df["close"].shift(1)
    prev_sma = df[sma].shift(1)

    # Long: price below SMA, now rejecting back above (close > SMA, previous close < SMA)
    long_reject = (prev_close < prev_sma) & (df["close"] > df[sma]) & (df["low"] <= df[sma])
    # Short: price above SMA, now rejecting back below
    short_reject = (prev_close > prev_sma) & (df["close"] < df[sma]) & (df["high"] >= df[sma])

    signals[long_reject] = 1
    signals[short_reject] = -1
    return signals


def detect_breakout(df: pd.DataFrame, cfg: Config) -> pd.Series:
    """Breakout from N-bar range (highest high / lowest low)."""
    lookback = cfg.breakout_bars
    if len(df) < lookback + 2:
        return pd.Series(0, index=df.index)

    signals = pd.Series(0, index=df.index)
    rolling_high = df["high"].rolling(lookback).max().shift(1)
    rolling_low = df["low"].rolling(lookback).min().shift(1)

    # Long: close breaks above range high
    long_break = (df["close"] > rolling_high) & (df["close"].shift(1) <= rolling_high.shift(1))
    # Short: close breaks below range low
    short_break = (df["close"] < rolling_low) & (df["close"].shift(1) >= rolling_low.shift(1))

    signals[long_break] = 1
    signals[short_break] = -1
    return signals


# ── Trade Engine ──────────────────────────────────────────────────────────────

@dataclass
class Trade:
    entry_bar: int
    direction: str          # "long" / "short"
    entry_price: float
    sl_price: float
    tp_price: float
    exit_bar: int = 0
    exit_price: float = 0.0
    pnl: float = 0.0
    closed: bool = False
    reason: str = ""


@dataclass
class Metrics:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_dd: float = 0.0
    total_return: float = 0.0


def run_backtest(df: pd.DataFrame, cfg: Config) -> tuple[List[Trade], Metrics]:
    """Run backtest on a single dataframe with given config."""
    df = df.copy()
    if len(df) < 100:
        return [], Metrics()

    # Add indicators
    df = add_ema(df, cfg.ema_fast)
    df = add_ema(df, cfg.ema_slow)
    df = add_sma(df, cfg.sma_period)
    df = add_rsi(df, cfg.rsi_period)
    df = add_atr(df, 14)

    # Bias: check trend on bias TF ema
    bias_col = f"ema_{cfg.ema_slow}"

    # Detect signals
    signal_fn = {
        "ema_cross": detect_ema_cross,
        "rsi_reversal": detect_rsi_reversal,
        "sma_pullback": detect_sma_pullback,
        "breakout": detect_breakout,
    }.get(cfg.strategy)

    if signal_fn is None:
        return [], Metrics()

    df["signal"] = signal_fn(df, cfg)

    # Run the trade loop
    trades: List[Trade] = []
    equity = 1.0  # normalized
    peak = 1.0
    metrics = Metrics()
    capital = 10_000.0
    balance = capital

    # Cost model for indices (wider ticks)
    tick_size = 0.01
    spread_ticks = 1.0

    for i in range(50, len(df)):
        row = df.iloc[i]

        # Check bias filter
        bias_bull = row.get(bias_col, 0) < row["close"]
        bias_bear = row.get(bias_col, 0) > row["close"]

        # Signal logic (always check)
        sig = row["signal"]

        if sig == 1 and bias_bull:
            # Long entry
            entry = row["close"] + spread_ticks * tick_size
            atr = row["atr"] if row["atr"] > 0 else row["atr"] * 0 + 10
            sl = entry - cfg.sl_atr * atr
            tp = entry + cfg.rr * (entry - sl)
            trade = Trade(
                entry_bar=i, direction="long",
                entry_price=entry, sl_price=sl, tp_price=tp,
            )
            trades.append(trade)

        elif sig == -1 and bias_bear:
            # Short entry
            entry = row["close"] - spread_ticks * tick_size
            atr = row["atr"] if row["atr"] > 0 else 10
            sl = entry + cfg.sl_atr * atr
            tp = entry - cfg.rr * (sl - entry)
            trade = Trade(
                entry_bar=i, direction="short",
                entry_price=entry, sl_price=sl, tp_price=tp,
            )
            trades.append(trade)

        # Check open trades
        for t in trades:
            if t.closed:
                continue
            if t.direction == "long":
                if row["low"] <= t.sl_price:
                    t.exit_bar = i
                    t.exit_price = t.sl_price - spread_ticks * tick_size
                    t.pnl = (t.exit_price - t.entry_price) / t.entry_price * balance * cfg.risk_pct * 20
                    t.closed = True
                    t.reason = "sl"
                elif row["high"] >= t.tp_price:
                    t.exit_bar = i
                    t.exit_price = t.tp_price
                    t.pnl = (t.exit_price - t.entry_price) / t.entry_price * balance * cfg.risk_pct * 20
                    t.closed = True
                    t.reason = "tp"
            else:  # short
                if row["high"] >= t.sl_price:
                    t.exit_bar = i
                    t.exit_price = t.sl_price + spread_ticks * tick_size
                    t.pnl = (t.entry_price - t.exit_price) / t.entry_price * balance * cfg.risk_pct * 20
                    t.closed = True
                    t.reason = "sl"
                elif row["low"] <= t.tp_price:
                    t.exit_bar = i
                    t.exit_price = t.tp_price
                    t.pnl = (t.entry_price - t.exit_price) / t.entry_price * balance * cfg.risk_pct * 20
                    t.closed = True
                    t.reason = "tp"

        # If bar[i] closes open trades, also check for time stop (hold too long)
        # Not implemented — keep it simple for now

        # Update equity for closed trades
        for t in trades:
            if t.closed and t.exit_bar == i:
                balance += t.pnl
                if t.pnl > 0:
                    metrics.wins += 1
                    metrics.gross_profit += t.pnl
                else:
                    metrics.losses += 1
                    metrics.gross_loss += abs(t.pnl)

    metrics.total_trades = len(trades)
    closed = [t for t in trades if t.closed]
    if closed:
        metrics.total_return = ((balance - capital) / capital) * 100

        # Simple max drawdown on trade equity
        equity_curve = [capital]
        for t in sorted(closed, key=lambda x: x.exit_bar):
            equity_curve.append(equity_curve[-1] + t.pnl)
        equity_series = pd.Series(equity_curve)
        peak_series = equity_series.cummax()
        dd_series = (equity_series - peak_series) / peak_series * 100
        metrics.max_dd = abs(dd_series.min()) if len(dd_series) > 0 else 0

    return trades, metrics


def print_metrics(cfg: Config, metrics: Metrics, duration_s: float):
    """Print results row."""
    wr = (metrics.wins / metrics.total_trades * 100) if metrics.total_trades > 0 else 0
    pf = (metrics.gross_profit / metrics.gross_loss) if metrics.gross_loss > 0 else float('inf')

    name = cfg.label()
    print(f"  {name:<40s} | "
          f"n={metrics.total_trades:<4d} | "
          f"WR={wr:5.1f}% | "
          f"PF={pf:6.2f} | "
          f"Ret={metrics.total_return:+7.2f}% | "
          f"DD={metrics.max_dd:5.1f}% | "
          f"{duration_s:5.1f}s")


# ── Run Modes ─────────────────────────────────────────────────────────────────

def run_single(days: int = 30):
    """Run a small set of configs."""
    configs = [
        Config(strategy="ema_cross", rr=2.0),
        Config(strategy="ema_cross", entry_tf="30", rr=2.0),
        Config(strategy="rsi_reversal", rr=1.5),
        Config(strategy="rsi_reversal", entry_tf="30", rr=1.5),
        Config(strategy="sma_pullback", rr=2.0),
        Config(strategy="sma_pullback", entry_tf="30", rr=2.0),
        Config(strategy="breakout", rr=1.5),
        Config(strategy="breakout", entry_tf="30", rr=1.5),
    ]

    print(f"\nNAS100 — {days} day window — Single Run")
    print(f"{'─' * 100}")
    results = []

    for cfg in configs:
        t0 = time.time()
        df = load_nas100(cfg.entry_tf, days=days)
        if len(df) < 100:
            print(f"  ⚠ Not enough data for {cfg.entry_tf}: {len(df)} rows")
            continue
        trades, metrics = run_backtest(df, cfg)
        dt = time.time() - t0
        print_metrics(cfg, metrics, dt)
        results.append((cfg, metrics))

    # Sort by PF
    results.sort(key=lambda x: x[1].gross_profit / max(x[1].gross_loss, 0.01), reverse=True)
    print(f"\n{'─' * 100}")
    print("Ranked by Profit Factor:")
    for cfg, m in results[:5]:
        pf = m.gross_profit / max(m.gross_loss, 0.01)
        print(f"  {cfg.label():<40s} PF={pf:6.2f}  WR={m.wins/max(m.total_trades,1)*100:5.1f}%  n={m.total_trades}")


def run_sweep(days: int = 30):
    """Full config sweep across strategies, TFs, RRs."""
    print(f"\nNAS100 — {days} day window — Full Sweep")
    print(f"{'─' * 120}")

    configs = []
    for strat in STRATEGIES:
        for etf in ENTRY_TFS:
            for btf in BIAS_TFS:
                for rr in RR_VALUES:
                    configs.append(Config(
                        strategy=strat, entry_tf=etf, bias_tf=btf, rr=rr,
                    ))

    results = []
    for cfg in configs:
        t0 = time.time()
        df = load_nas100(cfg.entry_tf, days=days)
        if len(df) < 100:
            continue
        trades, metrics = run_backtest(df, cfg)
        dt = time.time() - t0
        if metrics.total_trades > 0:
            print_metrics(cfg, metrics, dt)
            results.append((cfg, metrics))

    # Summary
    pf_sorted = sorted(
        [r for r in results if r[1].gross_loss > 0],
        key=lambda x: x[1].gross_profit / x[1].gross_loss, reverse=True
    )
    wr_sorted = sorted(results, key=lambda x: x[1].wins / max(x[1].total_trades, 1), reverse=True)
    dd_sorted = sorted(results, key=lambda x: x[1].max_dd)

    print(f"\n{'═' * 120}")
    print("Top 5 by Profit Factor:")
    for cfg, m in pf_sorted[:5]:
        pf = m.gross_profit / m.gross_loss
        print(f"  {cfg.label():<40s} PF={pf:6.2f}  n={m.total_trades}  WR={m.wins/max(m.total_trades,1)*100:5.1f}%  DD={m.max_dd:5.1f}%  Ret={m.total_return:+7.2f}%")

    print(f"\nTop 5 by Win Rate (min 10 trades):")
    for cfg, m in [x for x in wr_sorted if x[1].total_trades >= 10][:5]:
        wr = m.wins / m.total_trades * 100
        print(f"  {cfg.label():<40s} WR={wr:5.1f}%  n={m.total_trades}  PF={m.gross_profit/max(m.gross_loss,0.01):6.2f}  DD={m.max_dd:5.1f}%")

    print(f"\nTop 5 by Lowest Drawdown (min 10 trades):")
    for cfg, m in [x for x in dd_sorted if x[1].total_trades >= 10][:5]:
        print(f"  {cfg.label():<40s} DD={m.max_dd:5.1f}%  n={m.total_trades}  WR={m.wins/m.total_trades*100:5.1f}%")

    # Save to CSV
    rows = []
    for cfg, m in results:
        rows.append({
            "strategy": cfg.strategy,
            "entry_tf": cfg.entry_tf,
            "bias_tf": cfg.bias_tf,
            "rr": cfg.rr,
            "trades": m.total_trades,
            "wins": m.wins,
            "win_rate_pct": round(m.wins / max(m.total_trades, 1) * 100, 1),
            "profit_factor": round(m.gross_profit / max(m.gross_loss, 0.01), 2),
            "return_pct": round(m.total_return, 2),
            "max_dd_pct": round(m.max_dd, 2),
        })

    out = _ROOT / "data" / "nas100_sweep_results.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nResults saved to {out}")


def run_monthly(days_per_window: int = 30):
    """Rolling monthly windows to test stability."""
    print(f"\nNAS100 — Rolling {days_per_window}-day Windows")
    print(f"{'─' * 100}")

    # Best config from quick/default tests — user can adjust
    configs = [
        Config(strategy="ema_cross", rr=2.0),
        Config(strategy="rsi_reversal", rr=1.5),
    ]

    # Load full data, split into non-overlapping windows
    full = load_nas100("60", days=360)  # ~1 year
    if len(full) < 500:
        print("  ⚠ Not enough full data for monthly rolling")
        return

    start = full["ts"].min()
    end = full["ts"].max()
    window = timedelta(days=days_per_window)
    step = timedelta(days=days_per_window)  # non-overlapping
    cursor = start

    all_rows = []
    while cursor + window <= end:
        w_end = cursor + window
        w_data = full[(full["ts"] >= cursor) & (full["ts"] < w_end)].copy()
        if len(w_data) < 100:
            cursor += step
            continue

        label = f"{cursor.date()} → {w_end.date()}"
        for cfg in configs:
            t0 = time.time()
            trades, m = run_backtest(w_data, cfg)
            dt = time.time() - t0
            if m.total_trades > 0:
                wr = m.wins / m.total_trades * 100
                pf = m.gross_profit / max(m.gross_loss, 0.01)
                print(f"  {cfg.label():<25s}  {label:<28s}  "
                      f"n={m.total_trades:<3d}  WR={wr:5.1f}%  PF={pf:6.2f}  DD={m.max_dd:5.1f}%")
                all_rows.append({
                    "window": label, "config": cfg.label(), "trades": m.total_trades,
                    "wr": round(wr, 1), "pf": round(pf, 2), "dd": round(m.max_dd, 1),
                })

        cursor += step

    if all_rows:
        out = _ROOT / "data" / "nas100_monthly_results.csv"
        pd.DataFrame(all_rows).to_csv(out, index=False)
        print(f"\nResults saved to {out}")

    # Summary stats per config
    if all_rows:
        df = pd.DataFrame(all_rows)
        print(f"\n{'─' * 60}")
        print("Aggregate by config:")
        for cfg_name in df["config"].unique():
            sub = df[df["config"] == cfg_name]
            print(f"  {cfg_name:<25s} avg WR={sub['wr'].mean():5.1f}%  "
                  f"avg PF={sub['pf'].mean():6.2f}  avg DD={sub['dd'].mean():5.1f}%  "
                  f"windows={len(sub)}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="NAS100 Backtest")
    parser.add_argument("--days", type=int, default=30, help="Data window (days)")
    parser.add_argument("--sweep", action="store_true", help="Full config sweep")
    parser.add_argument("--monthly", action="store_true", help="Rolling monthly windows")
    args = parser.parse_args()

    if args.sweep:
        run_sweep(days=args.days)
    elif args.monthly:
        run_monthly(days_per_window=args.days)
    else:
        run_single(days=args.days)


if __name__ == "__main__":
    main()
