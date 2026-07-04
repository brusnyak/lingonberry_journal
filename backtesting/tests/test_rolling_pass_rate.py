from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.analysis.rolling_pass_rate import rolling_window_pass_rate
from backtesting.prop.rules import PropAccount

ACCT = PropAccount(name="test", initial_equity=10_000, daily_dd_pct=0.05,
                   max_dd_pct=0.10, target_pct=0.08)


def _trades(pnls: list[float], start="2026-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(pnls), freq="D")
    return pd.DataFrame({"exit_time": dates, "pnl": pnls})


def test_clean_pass_detected():
    # +1000 on day 5 of a 60-day series -> 10% gain, clears 8% target, no DD
    pnls = [50] * 5 + [1000] + [10] * 54
    tr = _trades(pnls)
    r = rolling_window_pass_rate(tr, ACCT, window_days=30, step_days=5)
    assert r.n_passed > 0
    assert r.pass_rate > 0


def test_breach_detected():
    # -1500 immediately -> 15% loss, breaches 10% max DD before any target
    pnls = [-1500] + [10] * 59
    tr = _trades(pnls)
    r = rolling_window_pass_rate(tr, ACCT, window_days=30, step_days=5)
    assert r.n_breached > 0


def test_neither_when_flat():
    pnls = [1] * 60
    tr = _trades(pnls)
    r = rolling_window_pass_rate(tr, ACCT, window_days=30, step_days=5)
    assert r.n_neither == r.n_windows


def test_empty_trades_returns_zero():
    r = rolling_window_pass_rate(pd.DataFrame(columns=["exit_time", "pnl"]), ACCT)
    assert r.n_windows == 0
    assert r.pass_rate == 0.0
