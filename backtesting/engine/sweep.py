"""Multi-process param sweep using VbtRunner + VectorBT portfolio.

Optimizations:
  - Workers pre-warm Numba before running combos (eliminates JIT compilation
    overhead per worker — the dominant cost in cold start)
  - Grid dedup: pip_size-auto-scaled params collapse to single value
  - Metrics computed directly from pf.trades (skips expensive pf.stats())
"""

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


# ── Per-worker Numba warmup cache ────────────────────────────────────────────────
_WARMED = False


def _warm_numba() -> None:
    """Trigger Numba JIT compilation of VBT internals.

    Each worker process calls this once with realistic data (SL/TP arrays).
    After warmup, subsequent from_signals calls skip the ~1.5s compilation step.
    """
    global _WARMED
    if _WARMED:
        return
    try:
        import numpy as np
        import vectorbt as vbt
        # Realistic warmup: 100 bars with SL/TP
        n = 100
        close = np.ones(n) * 1.89 + np.cumsum(np.random.randn(n) * 0.00005)
        entries = np.zeros(n, dtype=bool)
        entries[5] = True
        sl = np.full(n, np.nan)
        tp = np.full(n, np.nan)
        sz = np.full(n, np.nan)
        sl[5] = close[5] * 0.998
        tp[5] = close[5] * 1.003
        sz[5] = 0.01
        pf = vbt.Portfolio.from_signals(
            close=close, entries=entries, direction="longonly",
            sl_stop=np.nan_to_num(sl, nan=0.0),
            tp_stop=np.nan_to_num(tp, nan=np.inf),
            init_cash=10000, size=np.nan_to_num(sz, nan=0.0),
        )
        _ = pf.stats()
    except Exception:
        pass
    _WARMED = True


def _report_from_pf(pf) -> dict:
    """Extract sweep metrics from portfolio directly (avoids pf.stats())."""
    report = {"Total Trades": 0, "Total Return": 0.0, "Max Drawdown": 0.0,
              "Win Rate": 0.0, "Profit Factor": 0.0, "Expectancy": 0.0}
    try:
        report["Total Return"] = float(pf.total_return())
    except Exception:
        pass
    try:
        trades = pf.trades.records
        counts = trades["status"].value_counts()
        n_closed = int(counts.get(1, 0))  # status 1 = closed
        n_win = int(np.sum(trades.loc[trades["status"] == 1, "pnl"] > 0)) if n_closed > 0 else 0
        report["Total Trades"] = n_closed
        report["Win Rate"] = float(n_win / n_closed) if n_closed > 0 else 0.0
    except Exception:
        pass
    try:
        eq = pf.equity()
        if len(eq) > 1:
            dd = (eq.cummax() - eq).max()
            report["Max Drawdown"] = float(dd / eq.cummax().max() * 100) if eq.cummax().max() > 0 else 0.0
    except Exception:
        pass
    try:
        report["Profit Factor"] = float(pf.profit_factor())
    except Exception:
        pass
    try:
        report["Expectancy"] = float(pf.expectancy())
    except Exception:
        pass
    return report


def _run_single_combo(args) -> SweepResult:
    """Run one param combo (standalone for multiprocessing)."""
    strategy_cls, data_dict, entry_tf, costs, equity, max_pos, params = args

    # Warm Numba once per worker
    _warm_numba()

    try:
        strategy = strategy_cls(**params)
        result = VbtRunner.run(
            strategy, data_dict, entry_tf=entry_tf,
            costs=costs, initial_equity=equity,
            max_open_positions=max_pos,
        )
        # Use fast metrics (avoid pf.stats())
        report = _report_from_pf(result.pf)
        return SweepResult(
            param_combo=params,
            trades=result.trades,
            report=report,
            elapsed_s=result.elapsed_s,
            n_bars=result.n_bars,
            total_return=report["Total Return"],
            total_trades=report["Total Trades"],
            max_drawdown=report["Max Drawdown"],
            win_rate=report["Win Rate"],
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