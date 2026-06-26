"""Crypto challenge reporting helpers.

These functions sit above the engine. They do not run strategies; they turn
closed trades into tables that are hard to game: window metrics, trade-level
PnL, and tiny-account challenge outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import pandas as pd

from backtesting.engine import metrics
from backtesting.engine.orders import ClosedTrade
from backtesting.engine.runner import BacktestResult


DEFAULT_WINDOWS = (30, 60, 90)


@dataclass(frozen=True)
class BacktestContext:
    strategy: str
    symbol: str
    exchange: str
    timeframe: str
    duration_days: int
    initial_equity: float = 20.0
    target_equity: float = 100.0
    ruin_equity: float = 0.0


def trades_to_frame(trades: Sequence[ClosedTrade]) -> pd.DataFrame:
    """Trade ledger with fields needed for later filtering/reporting."""
    rows = []
    for t in trades:
        duration_min = 0.0
        try:
            duration_min = (t.exit_time - t.entry_time).total_seconds() / 60
        except Exception:
            pass
        rows.append(
            {
                "id": t.id,
                "direction": t.direction.value if hasattr(t.direction, "value") else t.direction,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "duration_min": round(duration_min, 1),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "exit_reason": t.exit_reason.value if hasattr(t.exit_reason, "value") else t.exit_reason,
                "lots": t.lots,
                "pnl": round(t.pnl, 4),
                "r_multiple": round(t.r_multiple, 4),
                "label": t.label,
                "sl": getattr(t, "sl", 0.0),
                "tp1": getattr(t, "tp1", 0.0),
            }
        )
    return pd.DataFrame(rows)


def summary_row(
    trades: Sequence[ClosedTrade],
    context: BacktestContext,
    *,
    window_days: int | None = None,
) -> dict:
    report = metrics.compute(trades, initial_equity=context.initial_equity)
    challenge = challenge_outcome(
        trades,
        initial_equity=context.initial_equity,
        target_equity=context.target_equity,
        ruin_equity=context.ruin_equity,
    )
    return {
        "strategy": context.strategy,
        "exchange": context.exchange,
        "symbol": context.symbol,
        "timeframe": context.timeframe,
        "duration_days": context.duration_days if window_days is None else window_days,
        "window_days": window_days or context.duration_days,
        "trades": report["trades"],
        "win_rate": report["win_rate"],
        "payoff_ratio": report["payoff_ratio"],
        "profit_factor": report["profit_factor"],
        "avg_r": report["avg_r"],
        "expectancy": report["expectancy"],
        "pnl": report["total_pnl"],
        "return_pct": report["return_pct"],
        "final_equity": report["final_equity"],
        "max_dd": report["max_drawdown"],
        "max_dd_pct": report["max_drawdown_pct"],
        "best_trade": report["best_trade"],
        "worst_trade": report["worst_trade"],
        "avg_duration_min": report["avg_duration_min"],
        "median_duration_min": report["median_duration_min"],
        "target_hit": challenge["target_hit"],
        "ruin_hit": challenge["ruin_hit"],
        "days_to_target": challenge["days_to_target"],
        "trades_to_target": challenge["trades_to_target"],
    }


def build_report_tables(
    result: BacktestResult,
    context: BacktestContext,
    windows: Iterable[int] = DEFAULT_WINDOWS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (summary_df, trade_df)."""
    trades = sorted(result.trades, key=lambda t: t.exit_time)
    rows = [summary_row(trades, context)]
    if trades:
        end = max(pd.Timestamp(t.exit_time) for t in trades)
        for days in windows:
            start = end - pd.Timedelta(days=days)
            window_trades = [t for t in trades if pd.Timestamp(t.exit_time) >= start]
            rows.append(summary_row(window_trades, context, window_days=days))

    trade_df = trades_to_frame(trades)
    if not trade_df.empty:
        trade_df.insert(0, "strategy", context.strategy)
        trade_df.insert(1, "exchange", context.exchange)
        trade_df.insert(2, "symbol", context.symbol)
        trade_df.insert(3, "timeframe", context.timeframe)
        trade_df["cum_pnl"] = trade_df["pnl"].cumsum().round(4)
        trade_df["equity"] = (context.initial_equity + trade_df["cum_pnl"]).round(4)
    return pd.DataFrame(rows), trade_df


def challenge_outcome(
    trades: Sequence[ClosedTrade],
    *,
    initial_equity: float = 20.0,
    target_equity: float = 100.0,
    ruin_equity: float = 0.0,
) -> dict:
    equity = initial_equity
    peak = initial_equity
    max_dd = 0.0
    start_ts = pd.Timestamp(trades[0].entry_time) if trades else None
    target_hit = False
    ruin_hit = False
    target_ts = None
    target_trade = 0

    for idx, t in enumerate(sorted(trades, key=lambda x: x.exit_time), start=1):
        equity += t.pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        if not target_hit and equity >= target_equity:
            target_hit = True
            target_ts = pd.Timestamp(t.exit_time)
            target_trade = idx
        if equity <= ruin_equity:
            ruin_hit = True
            break

    days_to_target = None
    if target_ts is not None and start_ts is not None:
        days_to_target = round((target_ts - start_ts).total_seconds() / 86400, 2)

    return {
        "initial_equity": initial_equity,
        "target_equity": target_equity,
        "final_equity": round(equity, 4),
        "target_hit": target_hit,
        "ruin_hit": ruin_hit,
        "max_dd": round(max_dd, 4),
        "max_dd_pct": round(max_dd / peak, 4) if peak else 0.0,
        "days_to_target": days_to_target,
        "trades_to_target": target_trade if target_hit else 0,
    }
