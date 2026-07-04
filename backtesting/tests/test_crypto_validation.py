"""
Test crypto rolling window validation module.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.crypto.validation import rolling_validate, RollingValidation, print_validation_table


def _trades_df(exit_times: list[str], pnl: list[float], r_mult: list[float] | None = None) -> pd.DataFrame:
    """Build a trades DataFrame for testing."""
    df = pd.DataFrame({
        "exit_time": pd.to_datetime(exit_times),
        "pnl": pnl,
        "r_multiple": r_mult if r_mult else [1.0] * len(pnl),
    })
    return df


def test_empty_trades_returns_empty():
    vt = rolling_validate(pd.DataFrame(), window_days=30, step_days=10)
    assert vt.n_windows == 0
    assert vt.n_with_trades == 0
    assert vt.n_profitable == 0


def test_no_trades_in_any_window():
    """All trades outside the window bounds should yield 0 windows."""
    df = _trades_df(
        ["2024-01-01", "2024-01-02"],
        [100.0, 50.0],
    )
    vt = rolling_validate(df, window_days=30, step_days=10, min_trades=3)
    assert vt.n_windows == 0


def test_single_profitable_window():
    """Five profitable trades in one window spanning 35 days."""
    df = _trades_df(
        ["2024-01-02", "2024-01-10", "2024-01-18", "2024-01-26", "2024-02-03"],
        [100.0, 50.0, 75.0, 60.0, 80.0],
        r_mult=[2.0, 1.5, 1.8, 1.2, 2.5],
    )
    vt = rolling_validate(df, window_days=30, step_days=10, initial_equity=1000.0)
    assert vt.n_windows > 0
    assert vt.n_profitable == vt.n_windows  # all profitable
    assert vt.median_pf > 1.0


def test_mixed_windows():
    """One profitable window, one losing window."""
    df = _trades_df(
        ["2024-01-02", "2024-01-10", "2024-01-18", "2024-01-26", "2024-02-03",
         "2024-03-01", "2024-03-10", "2024-03-18", "2024-03-26", "2024-04-03"],
        [100, 50, 75, 60, 80,     # profitable cluster
         -50, -80, -60, -40, -70], # losing cluster
    )
    vt = rolling_validate(df, window_days=30, step_days=15, initial_equity=1000.0)
    assert vt.n_windows >= 2
    assert 0 < vt.frac_profitable < 1.0


def test_equity_based_return_dd():
    """With initial_equity, return_pct and max_dd_pct should be sensible."""
    df = _trades_df(
        ["2024-01-02", "2024-01-10", "2024-01-18", "2024-01-26", "2024-02-03"],
        [50.0, -20.0, 30.0, -10.0, 40.0],
    )
    vt = rolling_validate(df, window_days=30, step_days=10, initial_equity=200.0)
    assert vt.n_windows >= 1
    # Total PnL = 90, initial = 200 → return 45%
    w = vt.windows[0]
    assert w.total_return_pct > 0
    assert 0 < w.max_dd_pct < 1.0


def test_large_window_gap_creates_multiple_windows():
    """Spread trade times across 40 days to get multiple 15-day windows."""
    days = pd.date_range("2024-01-01", periods=100, freq="12h")  # 100 trades over 50 days
    df = _trades_df(
        [str(d) for d in days],
        [np.random.uniform(-50, 100) for _ in range(100)],
    )
    vt = rolling_validate(df, window_days=15, step_days=5, min_trades=3)
    assert vt.n_windows >= 2  # 50 days span / 5 step = ~10 windows expected


def test_inf_profit_factor_handling():
    """All-wins window should produce inf PF, median should use finite values."""
    df = _trades_df(
        ["2024-01-02", "2024-01-15", "2024-01-28", "2024-02-10", "2024-02-23"],
        [100.0, 50.0, 75.0, 60.0, 80.0],  # no losses
    )
    vt = rolling_validate(df, window_days=30, step_days=10, initial_equity=1000.0)
    assert vt.n_windows >= 1
    assert vt.median_pf > 0  # should not NaN-crash on inf


def test_validation_table_no_crash():
    """print_validation_table should handle empty and single entries without crash."""
    empty_vt = RollingValidation(n_windows=0, n_with_trades=0, n_profitable=0, windows=[])
    sample_vt = rolling_validate(
        _trades_df(["2024-01-02", "2024-01-05"], [10.0, 20.0]),
        window_days=30, step_days=10, initial_equity=100.0,
    )
    # Should not raise
    print_validation_table([("empty", empty_vt)], title="Empty test")
    print_validation_table([("sample", sample_vt)], title="Sample test")
    print_validation_table([("a", empty_vt), ("b", sample_vt)], title="Mixed test")


def test_min_trades_filters():
    """Windows with fewer than min_trades should be excluded."""
    # 2 trades — use min_trades=3 to exclude, min_trades=1 to include
    # Need trades spanning > window_days so windows are created
    df = _trades_df(
        ["2024-01-02", "2024-01-20"],
        [100.0, 50.0],
    )
    vt = rolling_validate(df, window_days=14, step_days=10, min_trades=3)
    assert vt.n_windows == 0  # only 2 trades, min_trades=3 excludes

    vt2 = rolling_validate(df, window_days=14, step_days=10, min_trades=1)
    assert vt2.n_windows >= 1
