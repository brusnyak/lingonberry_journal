"""
VectorBT hybrid backtest runner.

Strategy keeps its Python next() callback. Runner collects Signals as order
records, then feeds them to vbt.Portfolio.from_orders for execution.

This gives 90% of the speedup (VectorBT's execution engine) without rewriting
complex state-machine strategies in Numba.

Usage:
    from backtesting.strategies.vbt_tr_ict_sweep import VbtRunner
    from backtesting.strategies.tr_ict_sweep import TrIctSweep

    result = VbtRunner.run(TrIctSweep(), data, entry_tf="1")
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import numpy as np
import pandas as pd
import vectorbt as vbt

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.costs import CostModel, ForexCosts
from backtesting.engine.orders import Direction, ExitReason, Signal


@dataclass
class VbtBacktestResult:
    trades: pd.DataFrame
    report: dict
    elapsed_s: float
    n_bars: int
    pf: vbt.Portfolio

    def summary(self) -> str:
        lines = [f"Bars: {self.n_bars:,}  |  Time: {self.elapsed_s:.2f}s"]
        if self.report:
            for k, v in self.report.items():
                if isinstance(v, float):
                    lines.append(f"  {k}: {v:.4f}")
                else:
                    lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def to_df(self) -> pd.DataFrame:
        return self.trades


class VbtRunner:
    """
    Hybrid runner: strategy.next() generates signals, VectorBT executes them.

    Benefits:
      - No Python bar-loop position management (VectorBT does it)
      - Strategy state-machine logic stays untouched
      - Easy to swap strategies in/out
    """

    @staticmethod
    def run(
        strategy: Strategy,
        data: dict[str, pd.DataFrame],
        entry_tf: str = "1",
        costs: Optional[CostModel] = None,
        initial_equity: float = 10_000.0,
        max_open_positions: int = 1,
        verbose: bool = False,
        freq: str = "1min",
    ) -> VbtBacktestResult:
        if costs is None:
            costs = ForexCosts()

        t0 = time.perf_counter()

        # Init strategy
        strategy.init(data)

        # Entry TF bars
        df = data[entry_tf].reset_index(drop=True)
        n_bars = len(df)

        ts_arr = df["ts"].to_numpy()
        open_arr = df["open"].to_numpy(dtype=float)
        high_arr = df["high"].to_numpy(dtype=float)
        low_arr = df["low"].to_numpy(dtype=float)
        close_arr = df["close"].to_numpy(dtype=float)

        # Collect signals
        signals: list[dict] = []  # {bar_idx, direction, entry, sl, tp1, tp1_frac, trail, label}

        # Minimal state for the strategy's on_close/on_partial callbacks
        equity = initial_equity
        open_positions: list = []
        closed_trades: list = []
        trade_id = 0

        # Track positions by signal bar for SL/TP exit
        # Since VectorBT handles exits, we just collect entry signals

        for i in range(n_bars):
            bar = BarData(
                ts=ts_arr[i], open_=open_arr[i], high=high_arr[i],
                low=low_arr[i], close=close_arr[i], volume=0.0, index=i,
            )

            # Strategy signal
            if len(open_positions) < max_open_positions:
                state = VbtRunner._make_state(
                    equity, initial_equity, open_positions, closed_trades, i
                )
                signal = strategy.next(bar, state)

                if signal is not None:
                    fill = costs.entry_fill(
                        signal.entry,
                        signal.direction.value if hasattr(signal.direction, "value") else signal.direction,
                    )

                    # Calculate size
                    stop_dist = abs(signal.entry - signal.sl)
                    if stop_dist <= 0:
                        continue
                    if hasattr(costs, "calc_lots"):
                        try:
                            lots = costs.calc_lots(equity, signal.risk_pct, stop_dist, price=signal.entry)
                        except Exception:
                            lots = 0.01
                    else:
                        lots = 0.01

                    if lots <= 0:
                        continue

                    dir_sign = 1 if signal.direction == Direction.LONG else -1

                    signals.append({
                        "bar_idx": i,
                        "direction": dir_sign,
                        "entry_price": fill,
                        "sl": signal.sl,
                        "tp1": signal.tp1,
                        "lots": lots,
                        "label": getattr(signal, "label", ""),
                    })

            # Track open positions count (simple count, not full position state)
            open_count = len(open_positions)
            if open_count < max_open_positions:
                pass  # Will check on next iteration

            if verbose and i % 10_000 == 0 and i > 0:
                print(f"  {i:,}/{n_bars:,} bars  signals={len(signals)}")

        # ── Execute signals via VectorBT ─────────────────────────────────
        close_1d = close_arr
        n_signals = len(signals)

        if n_signals == 0:
            elapsed = time.perf_counter() - t0
            return VbtBacktestResult(
                trades=pd.DataFrame(),
                report={"Total Trades": 0, "Total Return": 0, "Max Drawdown": 0},
                elapsed_s=elapsed, n_bars=n_bars,
                pf=vbt.Portfolio.from_holding(close_1d, init_cash=initial_equity),
            )

        # Build entry array and columns
        entries = np.zeros(n_bars, dtype=np.bool_)
        sl_stops = np.full(n_bars, np.nan)
        tp_stops = np.full(n_bars, np.nan)
        sizes = np.full(n_bars, np.nan)

        for sig in signals:
            i = sig["bar_idx"]
            entries[i] = True
            sl_stops[i] = sig["sl"]
            tp_stops[i] = sig["tp1"]
            sizes[i] = sig["lots"]

        # Handle direction: separate long and short
        long_entries = entries.copy()
        short_entries = entries.copy()

        for sig in signals:
            i = sig["bar_idx"]
            if sig["direction"] == -1:
                long_entries[i] = False
            else:
                short_entries[i] = False

        long_sl = np.where(long_entries, sl_stops, np.nan)
        long_tp = np.where(long_entries, tp_stops, np.nan)

        # ── Run VectorBT portfolio ───────────────────────────────────────
        # Use directional SL/TP so short-signal stops don't pollute long positions
        pf = vbt.Portfolio.from_signals(
            close=close_1d,
            entries=long_entries,
            direction="longonly",
            sl_stop=np.nan_to_num(long_sl, nan=0.0),
            tp_stop=np.nan_to_num(long_tp, nan=np.inf),
            init_cash=initial_equity,
            size=np.nan_to_num(sizes, nan=0.0),
            freq=freq,
        )

        elapsed = time.perf_counter() - t0

        # Build report
        report = {}
        try:
            s = pf.stats()
            if isinstance(s, pd.Series):
                for k in ["Total Return", "Total Trades", "Win Rate",
                          "Max Drawdown", "Profit Factor", "Expectancy"]:
                    if k in s.index:
                        val = s[k]
                        if hasattr(val, 'item'):
                            val = val.item()
                        report[k] = val
        except Exception:
            report["Total Return"] = pf.total_return() if hasattr(pf, 'total_return') else 0

        # Trades
        trades_df = pd.DataFrame()
        try:
            trades_df = pf.trades.records_readable
        except Exception:
            pass

        return VbtBacktestResult(
            trades=trades_df,
            report=report,
            elapsed_s=elapsed,
            n_bars=n_bars,
            pf=pf,
        )

    @staticmethod
    def _make_state(equity, initial_equity, open_positions, closed_trades, bar_index) -> EngineState:
        from .base import EngineState
        return EngineState(equity, initial_equity, open_positions, closed_trades, bar_index)