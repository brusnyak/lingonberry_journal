"""Multi-process param sweep using VbtRunner + VectorBT portfolio."""

from __future__ import annotations

import itertools
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import vectorbt as vbt

from backtesting.engine.costs import ForexCosts
from backtesting.engine.data import load_data
from backtesting.engine.vbt_runner import VbtRunner


@dataclass
class SweepResult:
    """Result of a param sweep run."""
    param_combo: dict
    trades: pd.DataFrame
    report: dict
    elapsed_s: float
    n_bars: int
    total_return: float
    total_trades: int
    max_drawdown: float
    win_rate: float

    @staticmethod
    def empty(params: dict) -> "SweepResult":
        return SweepResult(
            param_combo=params,
            trades=pd.DataFrame(),
            report={},
            elapsed_s=0.0, n_bars=0,
            total_return=0.0, total_trades=0,
            max_drawdown=0.0, win_rate=0.0,
        )


@dataclass
class SweepSummary:
    """Summary of all sweep results."""
    results: list[SweepResult]
    elapsed_s: float
    n_combos: int

    @property
    def df(self) -> pd.DataFrame:
        rows = []
        for r in self.results:
            row = dict(r.param_combo)
            row.update({
                "total_return": r.total_return,
                "total_trades": r.total_trades,
                "max_drawdown": r.max_drawdown,
                "win_rate": r.win_rate,
                "elapsed_s": r.elapsed_s,
            })
            rows.append(row)
        return pd.DataFrame(rows).sort_values("total_return", ascending=False)

    def best(self, metric: str = "total_return", min_trades: int = 5) -> SweepResult:
        """Return best result by metric, filtering by min_trades."""
        valid = [r for r in self.results if r.total_trades >= min_trades]
        if not valid:
            return SweepResult.empty({})
        return max(valid, key=lambda r: getattr(r, metric, r.total_return))


def _run_single_combo(args) -> SweepResult:
    """Run one param combo (standalone for multiprocessing)."""
    strategy_cls, data_dict, entry_tf, costs, equity, max_pos, params = args

    try:
        strategy = strategy_cls(**params)
        result = VbtRunner.run(
            strategy, data_dict, entry_tf=entry_tf,
            costs=costs, initial_equity=equity,
            max_open_positions=max_pos,
        )
        return SweepResult(
            param_combo=params,
            trades=result.trades,
            report=result.report,
            elapsed_s=result.elapsed_s,
            n_bars=result.n_bars,
            total_return=result.report.get("Total Return", 0),
            total_trades=result.report.get("Total Trades", 0),
            max_drawdown=result.report.get("Max Drawdown", 0),
            win_rate=result.report.get("Win Rate", 0),
        )
    except Exception as e:
        warnings.warn(f"Failed combo {params}: {e}")
        return SweepResult.empty(params)


def sweep_params(
    strategy_cls: type,
    symbol: str = "GBPAUD",
    entry_tf: str = "1",
    param_grid: Optional[dict] = None,
    initial_equity: float = 10_000.0,
    max_open_positions: int = 1,
    days: int = 30,
    max_workers: int = 4,
) -> SweepSummary:
    """
    Run a param sweep across a grid.

    Loads data once, then runs each combo in parallel (or sequentially).
    """
    if param_grid is None:
        param_grid = {}

    t0 = time.perf_counter()

    # Load data once
    data = {
        "1": load_data(symbol, "1", days=days),
        "15": load_data(symbol, "15", days=days),
        "240": load_data(symbol, "240", days=days),
    }
    if data["1"].empty:
        raise SystemExit(f"No 1m data for {symbol}")

    # Build param product
    keys = list(param_grid.keys())
    vals = list(param_grid.values())
    combos = [dict(zip(keys, c)) for c in itertools.product(*vals)]
    n_combos = len(combos)

    if n_combos == 0:
        combos = [{}]
        n_combos = 1

    costs = ForexCosts()
    args_list = [
        (strategy_cls, data, entry_tf, costs, initial_equity, max_open_positions, c)
        for c in combos
    ]

    results = []
    if max_workers > 1 and n_combos > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_run_single_combo, a) for a in args_list]
            for f in as_completed(futures):
                results.append(f.result())
    else:
        for a in args_list:
            results.append(_run_single_combo(a))

    elapsed = time.perf_counter() - t0

    return SweepSummary(results=results, elapsed_s=elapsed, n_combos=n_combos)


# ── Quick benchmark script ──────────────────────────────────────────────────────

def benchmark_sweep() -> None:
    """Benchmark param sweep speed."""
    from backtesting.strategies.tr_ict_sweep import TrIctSweep

    print("Benchmarking TrIctSweep param sweep...")
    t0 = time.perf_counter()

    summary = sweep_params(
        TrIctSweep,
        symbol="GBPAUD",
        entry_tf="1",
        days=5,  # small window for quick test
        param_grid={
            "swing_n": [3, 5],
            "mss_bars": [5, 10],
            "fvg_expiry_bars": [20, 40],
            "sl_buffer_pips": [10, 20],
            "tp1_r": [1.5, 2.0],
        },
        max_workers=1,
    )

    elapsed = time.perf_counter() - t0
    df = summary.df
    print(f"\nSweep: {summary.n_combos} combos in {elapsed:.1f}s ({elapsed/max(1,summary.n_combos):.2f}s/combo)")
    print(df.to_string(index=False))


if __name__ == "__main__":
    benchmark_sweep()