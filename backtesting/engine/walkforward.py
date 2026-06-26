"""
Walk-forward analysis — native multi-window IS/OOS validation.

Architecture:
  walkforward_run() — orchestrator
    ├─ WindowWalker — generates sliding (train, test) date pairs
    ├─ for each window:
    │   ├─ run all param combos on train period (IS optimization)
    │   ├─ pick best combo by chosen metric
    │   └─ run best combo on test period (OOS validation)
    └─ WalkForwardResult — aggregates all windows

Usage:
    from backtesting.engine.walkforward import walkforward_run, WindowWalker

    def make_strategy(params):
        return TrFvg(pip_size=0.001, **params)

    def load_data(start, end):
        return {
            "15": load_data(pair, "15", start, end, exchange="binance"),
            "240": load_data(pair, "240", start, end, exchange="binance"),
        }

    param_grid = [
        {"sl_buffer_pips": 15, "tp1_r": 1.5, "direction": "bull"},
        {"sl_buffer_pips": 20, "tp1_r": 2.0, "direction": "bull"},
    ]

    result = walkforward_run(
        strategy_factory=make_strategy,
        data_factory=load_data,
        param_grid=param_grid,
        train_days=60,
        test_days=30,
    )
    print(result.summary())
    result.results_df().to_csv("wf_results.csv")
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

import numpy as np
import pandas as pd

from . import metrics as metrics_mod
from .base import Strategy
from .costs import CostModel, ForexCosts
from .runner import BacktestResult, run


# ── Window iteration ────────────────────────────────────────────────────────


@dataclass
class Window:
    """A single (train, test) pair."""
    label: str
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime


class WindowWalker:
    """
    Generate sliding (train, test) window pairs.

    Default: non-overlapping walk-forward (step = test_days).
    Overlapping walk-forward uses step < test_days.

    Example (train=60, test=30, step=30):
        Window 0: train [Jan01–Mar02]  test [Mar02–Apr01]
        Window 1: train [Jan31–Apr01]  test [Apr01–Apr30]
        ...
    """

    def __init__(
        self,
        data_end: str | datetime,
        train_days: int = 60,
        test_days: int = 30,
        step_days: int = 30,
        data_start: str | datetime | None = None,
        min_test_bars: int = 500,
    ):
        if isinstance(data_end, str):
            data_end = datetime.strptime(data_end, "%Y-%m-%d")
        if isinstance(data_start, str):
            data_start = datetime.strptime(data_start, "%Y-%m-%d")
        if data_start is None:
            data_start = data_end - timedelta(days=train_days + test_days * 4)

        self.data_start = data_start
        self.data_end = data_end
        self.train_days = train_days
        self.test_days = test_days
        self.step_days = step_days
        self.min_test_bars = min_test_bars

    def __iter__(self):
        """Yield Window objects."""
        current = self.data_start
        while current + timedelta(days=self.train_days + self.test_days) <= self.data_end:
            train_start = current
            train_end = current + timedelta(days=self.train_days)
            test_start = train_end
            test_end = test_start + timedelta(days=self.test_days)

            if test_end > self.data_end:
                break

            label = (
                f"{train_start.strftime('%b%d')}-"
                f"{train_end.strftime('%b%d')}"
                f"→{test_start.strftime('%b%d')}-"
                f"{test_end.strftime('%b%d')}"
            )

            yield Window(
                label=label,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )

            current += timedelta(days=self.step_days)


# ── Single-window result ────────────────────────────────────────────────────


@dataclass
class WalkForwardWindowResult:
    """Results from one train/test window pair."""
    window: Window

    # IS (train) results
    is_best_params: dict
    is_best_metric_value: float
    is_n_configs: int
    is_best_report: dict
    is_elapsed_s: float

    # OOS (test) results
    oos_report: dict
    oos_trades: int
    oos_pnl: float
    oos_elapsed_s: float

    # Did the OOS validate?
    oos_positive: bool = False


# ── Aggregated result ───────────────────────────────────────────────────────


@dataclass
class WalkForwardResult:
    """Aggregated walk-forward results across all windows."""
    windows: list[WalkForwardWindowResult]

    # Aggregated OOS metrics
    total_oos_pnl: float = 0.0
    total_oos_trades: int = 0
    oos_win_rate: float = 0.0
    oos_profit_factor: float = 0.0
    oos_avg_r: float = 0.0
    oos_max_drawdown_pct: float = 0.0
    oos_valid_windows: int = 0
    positive_oos_windows: int = 0

    # Params stability
    param_stability: dict = field(default_factory=dict)

    elapsed_s: float = 0.0

    def __post_init__(self):
        self._aggregate()

    def _aggregate(self):
        """Compute aggregated OOS metrics from all windows."""
        all_oos_pnls: list[float] = []
        all_oos_rs: list[float] = []
        trades_per_window: list[int] = []
        oos_dds: list[float] = []

        for w in self.windows:
            if w.oos_trades < 3:
                continue
            all_oos_pnls.extend(w.oos_report.get("trade_pnls", []))
            all_oos_rs.extend(w.oos_report.get("trade_r_multiples", []))
            trades_per_window.append(w.oos_trades)
            oos_dds.append(w.oos_report.get("max_drawdown_pct", 0.0))

        self.total_oos_pnl = sum(all_oos_pnls)
        self.total_oos_trades = len(all_oos_pnls)
        self.oos_valid_windows = len([w for w in self.windows if w.oos_trades >= 3])
        self.positive_oos_windows = sum(1 for w in self.windows if w.oos_positive)

        if all_oos_pnls:
            wins = [p for p in all_oos_pnls if p > 0]
            losses = [p for p in all_oos_pnls if p <= 0]
            self.oos_win_rate = len(wins) / len(all_oos_pnls) if all_oos_pnls else 0.0
            self.oos_profit_factor = (
                sum(wins) / abs(sum(losses)) if losses else float("inf")
            )
            self.oos_avg_r = sum(all_oos_rs) / len(all_oos_rs) if all_oos_rs else 0.0

        if oos_dds:
            self.oos_max_drawdown_pct = max(oos_dds)

        # Param stability: how often did each param value get picked?
        if self.windows:
            param_keys = list(self.windows[0].is_best_params.keys())
            stability: dict[str, dict] = {}
            for k in param_keys:
                values = [w.is_best_params.get(k, None) for w in self.windows]
                from collections import Counter
                counts = Counter(values)
                top_val, top_count = counts.most_common(1)[0]
                stability[k] = {
                    "most_common": top_val,
                    "frequency": top_count / len(values) if values else 0.0,
                    "unique_values": len(counts),
                }
            self.param_stability = stability

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            "=" * 80,
            "WALK-FORWARD ANALYSIS",
            "=" * 80,
            f"  Windows: {len(self.windows)} total, "
            f"{self.oos_valid_windows} valid (≥3 OOS trades)",
            f"  Positive OOS windows: {self.positive_oos_windows}/{self.oos_valid_windows} "
            f"({(self.positive_oos_windows/max(self.oos_valid_windows,1))*100:.0f}%)",
            "",
            "  AGGREGATED OOS METRICS",
            f"    Trades:   {self.total_oos_trades}",
            f"    Win rate: {self.oos_win_rate:.1%}",
            f"    PF:       {self.oos_profit_factor:.2f}",
            f"    Avg R:    {self.oos_avg_r:.2f}R",
            f"    PnL:      ${self.total_oos_pnl:.2f}",
            f"    Max DD:   {self.oos_max_drawdown_pct:.1%}",
            "",
            "  PARAM STABILITY",
        ]
        for k, v in self.param_stability.items():
            lines.append(
                f"    {k:<25} {v['most_common']}  "
                f"(freq={v['frequency']:.0%}, "
                f"unique={v['unique_values']})"
            )

        lines.append("")
        lines.append("  PER-WINDOW BREAKDOWN")
        lines.append(
            f"    {'Window':<40} {'IS_best':<30} {'IS_PF':>6} "
            f"{'OOS_t':>4} {'OOS_PF':>6} {'OOS_PnL':>8} {'Valid':>5}"
        )
        lines.append("    " + "-" * 110)
        for w in self.windows:
            params_short = _params_str(w.is_best_params)
            is_pf = w.is_best_report.get("profit_factor", 0.0)
            oos_pf = w.oos_report.get("profit_factor", 0.0)
            valid = "✓" if w.oos_positive else "✗"
            lines.append(
                f"    {w.window.label:<40} {params_short:<30} "
                f"{is_pf:>5.2f} "
                f"{w.oos_trades:>4} {oos_pf:>5.2f} "
                f"{w.oos_pnl:>+7.2f} {valid:>5}"
            )

        lines.append("")
        lines.append(f"  Elapsed: {self.elapsed_s:.1f}s")
        return "\n".join(lines)

    def results_df(self) -> pd.DataFrame:
        """Per-window results as a DataFrame."""
        rows = []
        for w in self.windows:
            rows.append({
                "window": w.window.label,
                "train_start": w.window.train_start,
                "train_end": w.window.train_end,
                "test_start": w.window.test_start,
                "test_end": w.window.test_end,
                "best_params": str(w.is_best_params),
                "is_trades": w.is_best_report.get("trades", 0),
                "is_pf": w.is_best_report.get("profit_factor", 0.0),
                "is_wr": w.is_best_report.get("win_rate", 0.0),
                "is_dd": w.is_best_report.get("max_drawdown_pct", 0.0),
                "oos_trades": w.oos_trades,
                "oos_pf": w.oos_report.get("profit_factor", 0.0),
                "oos_wr": w.oos_report.get("win_rate", 0.0),
                "oos_avg_r": w.oos_report.get("avg_r", 0.0),
                "oos_pnl": w.oos_pnl,
                "oos_dd": w.oos_report.get("max_drawdown_pct", 0.0),
                "oos_positive": w.oos_positive,
            })
        return pd.DataFrame(rows)

    def param_matrix(self) -> pd.DataFrame:
        """Which param combo was picked each window — for stability analysis."""
        rows = []
        for w in self.windows:
            row = {"window": w.window.label}
            row.update(w.is_best_params)
            row["oos_pf"] = w.oos_report.get("profit_factor", 0.0)
            row["oos_pnl"] = w.oos_pnl
            rows.append(row)
        return pd.DataFrame(rows)


# ── Main orchestrator ───────────────────────────────────────────────────────


def walkforward_run(
    strategy_factory: Callable[[dict], Strategy],
    data_factory: Callable[[datetime, datetime], dict[str, pd.DataFrame]],
    param_grid: list[dict],
    train_days: int = 60,
    test_days: int = 30,
    step_days: int | None = None,
    entry_tf: str = "15",
    costs: Optional[CostModel] = None,
    initial_equity: float = 10_000.0,
    max_open_positions: int = 1,
    metric: str = "profit_factor",
    min_trades_is: int = 5,
    min_trades_oos: int = 3,
    verbose: bool = True,
) -> WalkForwardResult:
    """
    Run walk-forward analysis.

    Parameters
    ----------
    strategy_factory : callable(params_dict) -> Strategy
        Creates a fresh strategy for each run.
    data_factory : callable(start_date, end_date) -> dict[tf, DataFrame]
        Loads OHLC data for a date range.
    param_grid : list of dict
        Each dict is one param combination to test on IS windows.
    train_days : int
        In-sample (IS) window size in days.
    test_days : int
        Out-of-sample (OOS) window size in days.
    step_days : int or None
        Step between windows. Default = test_days (non-overlapping).
    entry_tf : str
        Key in data dict for the entry timeframe.
    costs : CostModel
        Default: ForexCosts().
    initial_equity : float
    max_open_positions : int
    metric : str
        Metric name from report dict to optimize on IS.
    min_trades_is : int
        Minimum trades required on IS to consider a config.
    min_trades_oos : int
        Minimum trades on OOS to count the window as valid.
    verbose : bool
    """
    if costs is None:
        costs = ForexCosts()
    if step_days is None:
        step_days = test_days

    t0 = time.perf_counter()

    # Determine data boundaries
    probe_data = data_factory(
        datetime(2020, 1, 1),
        datetime(2026, 12, 31),
    )
    probe_df = probe_data[entry_tf]
    data_start = probe_df["ts"].iloc[0] if "ts" in probe_df.columns else probe_df.index[0]
    data_end = probe_df["ts"].iloc[-1] if "ts" in probe_df.columns else probe_df.index[-1]
    if hasattr(data_start, "to_pydatetime"):
        data_start = data_start.to_pydatetime()
        data_end = data_end.to_pydatetime()

    walker = WindowWalker(
        data_end=data_end,
        train_days=train_days,
        test_days=test_days,
        step_days=step_days,
        data_start=data_start,
    )

    window_results: list[WalkForwardWindowResult] = []

    n_windows = 0
    for w in walker:
        n_windows += 1
        if verbose:
            print(f"\n[{n_windows}] {w.label}")
            print(f"      Train: {w.train_start.date()} → {w.train_end.date()}")
            print(f"      Test:  {w.test_start.date()} → {w.test_end.date()}")

        # ── IS: test all param combinations ──────────────────────────────
        is_results: list[tuple[dict, dict, float]] = []  # (params, report, elapsed)
        is_t0 = time.perf_counter()

        for i, params in enumerate(param_grid):
            try:
                strat = strategy_factory(params)
                data = data_factory(w.train_start, w.train_end)
                if data is None or entry_tf not in data:
                    continue
                result = run(
                    strat, data, entry_tf=entry_tf,
                    costs=costs, initial_equity=initial_equity,
                    max_open_positions=max_open_positions,
                )
                rep = result.report
                metric_val = rep.get(metric, 0.0)
                trades = rep.get("trades", 0)
                if trades >= min_trades_is:
                    is_results.append((params, rep, result.elapsed_s))
            except Exception as e:
                if verbose:
                    print(f"      ⚠ param skip ({params}): {e}")
                continue

        if not is_results:
            if verbose:
                print(f"      ⚠ No valid IS results — skipping window")
            continue

        # Pick best on IS
        is_results.sort(key=lambda x: x[1].get(metric, 0.0), reverse=True)
        best_params, best_report, best_elapsed = is_results[0]
        best_metric_val = best_report.get(metric, 0.0)

        if verbose:
            n_is_ok = len(is_results)
            print(f"      IS: {n_is_ok}/{len(param_grid)} valid  "
                  f"best=[{_params_str(best_params)}] "
                  f"{metric}={best_metric_val:.2f}  "
                  f"T={best_report.get('trades',0)}  "
                  f"PF={best_report.get('profit_factor',0):.2f}")

        # ── OOS: validate best params on test period ─────────────────────
        oos_t0 = time.perf_counter()
        try:
            oos_strat = strategy_factory(best_params)
            oos_data = data_factory(w.test_start, w.test_end)
            oos_result = run(
                oos_strat, oos_data, entry_tf=entry_tf,
                costs=costs, initial_equity=initial_equity,
                max_open_positions=max_open_positions,
            )
            oos_rep = oos_result.report
            oos_trades = oos_rep.get("trades", 0)
            oos_pnl = oos_rep.get("total_pnl", 0.0)
            oos_elapsed = oos_result.elapsed_s
            oos_positive = oos_pnl > 0 and oos_trades >= min_trades_oos
        except Exception as e:
            if verbose:
                print(f"      ⚠ OOS failed: {e}")
            oos_rep = metrics_mod.compute([], initial_equity)
            oos_trades = 0
            oos_pnl = 0.0
            oos_elapsed = 0.0
            oos_positive = False

        if verbose:
            oos_pf = oos_rep.get("profit_factor", 0.0)
            oos_wr = oos_rep.get("win_rate", 0.0)
            print(f"      OOS: T={oos_trades}  WR={oos_wr:.1%}  "
                  f"PF={oos_pf:.2f}  PnL=${oos_pnl:.2f}"
                  f"{'  ✓' if oos_positive else '  ✗'}")

        window_results.append(WalkForwardWindowResult(
            window=w,
            is_best_params=best_params,
            is_best_metric_value=best_metric_val,
            is_n_configs=len(is_results),
            is_best_report=best_report,
            is_elapsed_s=best_elapsed,
            oos_report=oos_rep,
            oos_trades=oos_trades,
            oos_pnl=oos_pnl,
            oos_elapsed_s=oos_elapsed,
            oos_positive=oos_positive,
        ))

    elapsed = time.perf_counter() - t0

    result = WalkForwardResult(
        windows=window_results,
        elapsed_s=elapsed,
    )

    if verbose:
        print(f"\n{result.summary()}")

    return result


# ── Helpers ─────────────────────────────────────────────────────────────────


def _params_str(params: dict) -> str:
    """Short string representation of a param dict."""
    parts = [f"{k}={v}" for k, v in sorted(params.items())]
    joined = " ".join(parts)
    return joined[:28]
