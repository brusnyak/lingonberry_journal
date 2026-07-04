"""
Rolling window validation for crypto backtest results.

Post-processing: run one full-dataset backtest, then slice the resulting
trades into overlapping rolling windows to check consistency.

Usage:
    result = run(strategy, data, ...)
    vt = rolling_validate(result.to_df(), window_days=60, step_days=10)
    print(vt.summary())

This answers: "if I traded this strategy for a random 60-day period, what
would my stats likely be?" without re-running the engine per window.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class WindowStats:
    start: pd.Timestamp
    end: pd.Timestamp
    trades: int
    profit_factor: float
    win_rate: float
    avg_r: float
    total_return_pct: float
    max_dd_pct: float
    total_pnl: float


@dataclass
class RollingValidation:
    """Aggregated results across all rolling windows."""
    n_windows: int
    n_with_trades: int
    n_profitable: int  # windows with PF > 1.0 AND total_return > 0
    windows: list[WindowStats] = field(repr=False)

    # Distribution stats
    median_pf: float = 0.0
    median_wr: float = 0.0
    median_avg_r: float = 0.0
    median_return_pct: float = 0.0
    median_max_dd_pct: float = 0.0
    median_trades: int = 0

    # Extremes
    best_return_pct: float = 0.0
    worst_return_pct: float = 0.0
    best_pf: float = 0.0
    worst_pf: float = 0.0  # among windows with trades
    best_dd: float = 0.0   # smallest drawdown (best = 0)
    worst_dd: float = 0.0

    # Summary rates
    frac_profitable: float = 0.0
    frac_positive_return: float = 0.0

    def summary(self) -> str:
        lines = [
            f"Rolling validation: {self.n_windows} windows, "
            f"{self.n_with_trades} with trades, "
            f"{self.n_profitable} profitable",
            "",
            f"  Median:  PF={self.median_pf:.2f}  WR={self.median_wr:.0%}  "
            f"avgR={self.median_avg_r:.2f}  ret={self.median_return_pct:.1%}  "
            f"DD={self.median_max_dd_pct:.1%}  T={self.median_trades}",
            f"  Range:   ret [{self.worst_return_pct:.1%}, {self.best_return_pct:.1%}]  "
            f"PF [{self.worst_pf:.2f}, {self.best_pf:.2f}]  "
            f"DD [{self.best_dd:.1%}, {self.worst_dd:.1%}]",
            f"  Rates:   profitable={self.frac_profitable:.0%}  "
            f"+return={self.frac_positive_return:.0%}",
        ]
        return "\n".join(lines)


def _compute_window_stats(trades: pd.DataFrame) -> WindowStats | None:
    """Compute metrics for a single window's trades."""
    if trades.empty:
        return None

    n = len(trades)
    pnl = trades["pnl"].values

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    n_wins = len(wins)
    n_losses = len(losses)

    total_pnl = float(pnl.sum())
    gross_win = float(wins.sum()) if n_wins > 0 else 0.0
    gross_loss = float(abs(losses.sum())) if n_losses > 0 else 0.0

    profit_factor = gross_win / gross_loss if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    win_rate = n_wins / n if n > 0 else 0.0

    r_multiples = trades["r_multiple"].values
    avg_r = float(r_multiples.mean())

    # Compute max drawdown from cumulative PnL
    cum = np.cumsum(pnl)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd = float(dd.max())

    # Total return as % of initial equity (approximated from PnL)
    # We don't have initial_equity here, so we estimate from the trade sequence
    # Use the equity at the start of the window (peak of cum before first drawdown? No.)
    # Simplest: express return relative to the running equity baseline
    # Actually, we can't compute accurate return% without knowing starting equity.
    # We'll store total_pnl and let the caller provide equity if needed.
    max_dd_pct = max_dd / (cum[0] + abs(max_dd) + 1e-9) if abs(max_dd) > 0 else 0.0

    return WindowStats(
        start=trades["exit_time"].min(),
        end=trades["exit_time"].max(),
        trades=n,
        profit_factor=profit_factor,
        win_rate=win_rate,
        avg_r=avg_r,
        total_return_pct=0.0,  # caller fills this
        max_dd_pct=0.0,  # synthetic equity needed
        total_pnl=total_pnl,
    )


def rolling_validate(
    trades: pd.DataFrame,
    window_days: int = 60,
    step_days: int = 10,
    min_trades: int = 3,
    initial_equity: float | None = None,
) -> RollingValidation:
    """
    Validate a strategy's consistency across rolling time windows.

    Parameters
    ----------
    trades : pd.DataFrame
        From BacktestResult.to_df(). Must have 'exit_time' and 'pnl' columns.
    window_days : int
        Length of each rolling window in calendar days.
    step_days : int
        Advance between window starts (1 = every day, 5 = every week, etc.)
    min_trades : int
        Minimum trades in a window to include it in stats.
    initial_equity : float, optional
        If provided, compute return% and drawdown% relative to this baseline.
    """
    if trades.empty:
        return RollingValidation(n_windows=0, n_with_trades=0, n_profitable=0, windows=[])

    tr = trades.sort_values("exit_time").reset_index(drop=True)
    tr["exit_time"] = pd.to_datetime(tr["exit_time"])
    first_day = tr["exit_time"].min().normalize()
    last_day = tr["exit_time"].max().normalize()

    windows: list[WindowStats] = []
    start = first_day

    while start + pd.Timedelta(days=window_days) <= last_day:
        end = start + pd.Timedelta(days=window_days)
        w = tr[(tr["exit_time"] >= start) & (tr["exit_time"] < end)].copy()
        if len(w) < min_trades:
            start += pd.Timedelta(days=step_days)
            continue

        pnl = w["pnl"].values
        n = len(pnl)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        n_wins = len(wins)
        n_losses = len(losses)
        total_pnl = float(pnl.sum())
        gross_win = float(wins.sum()) if n_wins > 0 else 0.0
        gross_loss = float(abs(losses.sum())) if n_losses > 0 else 0.0
        profit_factor = gross_win / gross_loss if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
        win_rate = n_wins / n if n > 0 else 0.0
        avg_r = float(w["r_multiple"].mean()) if "r_multiple" in w.columns else 0.0

        # Max drawdown from running equity curve
        cum = np.cumsum(pnl)

        # If initial_equity is given, use it as baseline
        if initial_equity is not None and initial_equity > 0:
            eq_curve = initial_equity + np.concatenate([[0], np.cumsum(pnl)[:-1]])
            # More accurate: equity before each trade
            eq_curve = np.full(n, initial_equity)
            eq_curve[1:] = initial_equity + np.cumsum(pnl)[:-1]
            dd = np.maximum.accumulate(eq_curve) - eq_curve
            max_dd_pct = float(dd.max()) / float(np.maximum.accumulate(eq_curve).max()) if len(eq_curve) > 0 else 0.0
            return_pct = total_pnl / initial_equity
        else:
            # PnL-only approximation: peak-to-trough ratio
            peak = np.maximum.accumulate(cum)
            dd = peak - cum
            max_dd_val = float(dd.max())
            max_dd_pct = max_dd_val / (peak[-1] + abs(max_dd_val) + 1e-9) if peak[-1] > 0 else 0.0
            return_pct = 0.0

        windows.append(WindowStats(
            start=start, end=end, trades=n,
            profit_factor=profit_factor, win_rate=win_rate,
            avg_r=avg_r, total_return_pct=return_pct,
            max_dd_pct=max_dd_pct, total_pnl=total_pnl,
        ))
        start += pd.Timedelta(days=step_days)

    n_win = len(windows)
    if n_win == 0:
        return RollingValidation(n_windows=0, n_with_trades=0, n_profitable=0, windows=[])

    pfs = np.array([w.profit_factor for w in windows])
    wrs = np.array([w.win_rate for w in windows])
    avgr = np.array([w.avg_r for w in windows])
    rets = np.array([w.total_return_pct for w in windows])
    dds = np.array([w.max_dd_pct for w in windows])
    tcounts = np.array([w.trades for w in windows])

    # Replace inf PF with large sentinel for median computation
    finite_only = pfs[np.isfinite(pfs)]
    has_inf = np.any(~np.isfinite(pfs))
    if len(finite_only) > 0:
        median_pf = float(np.median(finite_only))
        if has_inf:
            # At least one inf window — median is >= largest finite PF
            median_pf = max(median_pf, float(np.max(finite_only)) * 1.5)
    elif has_inf:
        median_pf = float('inf')  # all windows are inf PF
    else:
        median_pf = 0.0

    profitable = (pfs > 1.0) & (rets > 0)
    positive_return = rets > 0

    return RollingValidation(
        n_windows=n_win,
        n_with_trades=sum(1 for w in tcounts if w >= min_trades),
        n_profitable=int(profitable.sum()),
        windows=windows,
        median_pf=median_pf,
        median_wr=float(np.median(wrs)),
        median_avg_r=float(np.median(avgr)),
        median_return_pct=float(np.median(rets)),
        median_max_dd_pct=float(np.median(dds)),
        median_trades=int(np.median(tcounts)),
        best_return_pct=float(np.max(rets)),
        worst_return_pct=float(np.min(rets)),
        best_pf=float(np.max(finite_only)) if len(finite_only) > 0 else (float('inf') if has_inf else 0.0),
        worst_pf=float(np.min(finite_only)) if len(finite_only) > 0 else (float('inf') if has_inf else 0.0),
        best_dd=float(np.min(dds)),
        worst_dd=float(np.max(dds)),
        frac_profitable=float(profitable.mean()),
        frac_positive_return=float(positive_return.mean()),
    )


def print_validation_table(vals: list[tuple[str, RollingValidation]], title: str = ""):
    """Print a comparison table of validation results across configs."""
    if title:
        print(f"\n{'=' * 110}")
        print(f"  {title}")
        print(f"{'=' * 110}")

    header = (
        f"{'Config':<30} {'Win':>5} {'Win%':>5} {'PF':>5} {'avgR':>5} "
        f"{'Ret%':>6} {'DD%':>6} {'Ret[worst,best]':>20}"
    )
    print(header)
    print("-" * len(header))

    for label, vt in vals:
        if vt.n_windows == 0:
            print(f"{label:<30}  no windows with trades")
            continue
        ret_range = f"[{vt.worst_return_pct:.0%},{vt.best_return_pct:.0%}]"
        print(
            f"{label:<30} "
            f"{vt.n_profitable:>4}/{vt.n_windows} "
            f"{vt.median_wr:>4.0%} "
            f"{vt.median_pf:>4.2f} "
            f"{vt.median_avg_r:>4.2f} "
            f"{vt.median_return_pct:>5.1%} "
            f"{vt.median_max_dd_pct:>5.1%} "
            f"{ret_range:>20}"
        )
    print("-" * len(header))
