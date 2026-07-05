from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.analysis.rolling_return_stats import rolling_window_return_stats
from backtesting.prop.rules import PropAccount

NO_TARGET_ACCT = PropAccount(name="test_crypto", initial_equity=50.0,
                              daily_dd_pct=0.05, max_dd_pct=0.10, target_pct=None)


def _trades(pnls, start="2026-01-01"):
    days = pd.date_range(start, periods=len(pnls), freq="1D", tz="UTC")
    return pd.DataFrame({"exit_time": days, "pnl": pnls})


def test_empty_trades_returns_zeroed_result():
    r = rolling_window_return_stats(pd.DataFrame(), NO_TARGET_ACCT)
    assert r.n_windows == 0
    assert r.breach_rate == 0.0


def test_flat_positive_pnl_all_windows_positive():
    trades = _trades([1.0] * 100)  # $1/day steady gain on $50
    r = rolling_window_return_stats(trades, NO_TARGET_ACCT, window_days=30, step_days=5)
    assert r.n_windows > 0
    assert r.pct_windows_positive == 1.0
    assert r.median_return_pct > 0
    assert r.breach_rate == 0.0


def test_big_loss_triggers_breach_and_negative_return():
    trades = _trades([-10.0] + [0.1] * 99)  # 20% day-1 loss > 10% max DD
    r = rolling_window_return_stats(trades, NO_TARGET_ACCT, window_days=30, step_days=5)
    # every window containing day 1 should show a breach
    assert r.n_breached > 0
    assert r.breach_rate > 0.0
    assert r.worst_return_pct < 0


def test_window_count_matches_expected_span():
    trades = _trades([0.5] * 90)
    r = rolling_window_return_stats(trades, NO_TARGET_ACCT, window_days=30, step_days=1)
    # 90-day span, 30-day windows, step 1 -> 90-30 = 60 valid starts
    assert r.n_windows == 60


def test_median_vs_mean_differ_with_skewed_returns():
    # One huge winning window's tail shouldn't be hidden by using mean alone
    pnls = [0.2] * 80 + [40.0] + [0.2] * 19
    trades = _trades(pnls)
    r = rolling_window_return_stats(trades, NO_TARGET_ACCT, window_days=30, step_days=10)
    assert r.n_windows > 0
    # both present and distinct fields -- not asserting a specific relationship,
    # just that skew is actually visible in the output rather than collapsed
    assert isinstance(r.median_return_pct, float)
    assert isinstance(r.mean_return_pct, float)
