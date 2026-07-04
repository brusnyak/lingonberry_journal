"""
Reusable rolling-window prop-challenge pass-rate analysis.

Answers a different question than the cumulative discovery/holdout return
check we've been running: "if I started a real challenge attempt on a
RANDOM day, what fraction of the time would I hit the phase target within
N calendar days, without ever breaching the daily/max DD limit along the
way?" That's the actual speed-to-pass metric a prop challenge cares about,
not "what's the total return over 9 months."

Takes the trades DataFrame straight from `backtesting.engine.runner.run(...)
.to_df()` -- no separate backtest logic, this is pure post-processing of an
existing full-dataset run. One full backtest, sliced many ways, instead of
re-running the engine per window.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtesting.prop.rules import PropAccount


@dataclass
class RollingPassResult:
    n_windows: int
    n_passed: int
    n_breached: int
    n_neither: int  # window ended with neither target hit nor breach
    pass_rate: float
    median_days_to_pass: float | None
    breach_rate: float


def rolling_window_pass_rate(
    trades: pd.DataFrame,
    account: PropAccount,
    window_days: int = 30,
    step_days: int = 1,
) -> RollingPassResult:
    """
    trades: DataFrame with at least ['exit_time', 'pnl'] columns, sorted or
            not (will be sorted here), pnl computed at whatever position
            sizing the trades were originally run with -- caller is
            responsible for having run the backtest with the account's own
            initial_equity so $ pnl scales correctly.
    account: PropAccount (GFT_25K_2STEP / GFT_100K_1STEP / etc.)
    window_days: challenge phase length to test (default 30, i.e. "one
                 calendar month" per the user's question)
    step_days: how many days to advance the window start each iteration
               (1 = check every possible start day)
    """
    if trades.empty:
        return RollingPassResult(0, 0, 0, 0, 0.0, None, 0.0)

    tr = trades.sort_values("exit_time").reset_index(drop=True)
    tr["exit_time"] = pd.to_datetime(tr["exit_time"])
    first_day = tr["exit_time"].min().normalize()
    last_day = tr["exit_time"].max().normalize()

    results = []
    days_to_pass = []
    start = first_day
    while start + pd.Timedelta(days=window_days) <= last_day:
        end = start + pd.Timedelta(days=window_days)
        window_trades = tr[(tr["exit_time"] >= start) & (tr["exit_time"] < end)]

        equity = account.initial_equity
        peak = equity
        day_start_equity = equity
        cur_date = None
        passed = False
        breached = False
        days_elapsed_at_pass = None

        for _, t in window_trades.iterrows():
            d = t["exit_time"].normalize()
            if cur_date is None or d != cur_date:
                day_start_equity = equity
                cur_date = d
            equity += t["pnl"]
            peak = max(peak, equity)
            if account.check_daily_dd(equity, day_start_equity) or account.check_max_dd(equity, peak):
                breached = True
                break
            if account.check_target(equity):
                passed = True
                days_elapsed_at_pass = (d - start).days
                break

        results.append("pass" if passed else ("breach" if breached else "neither"))
        if passed and days_elapsed_at_pass is not None:
            days_to_pass.append(days_elapsed_at_pass)
        start += pd.Timedelta(days=step_days)

    n = len(results)
    n_pass = results.count("pass")
    n_breach = results.count("breach")
    n_neither = results.count("neither")
    return RollingPassResult(
        n_windows=n, n_passed=n_pass, n_breached=n_breach, n_neither=n_neither,
        pass_rate=round(n_pass / n, 3) if n else 0.0,
        median_days_to_pass=float(np.median(days_to_pass)) if days_to_pass else None,
        breach_rate=round(n_breach / n, 3) if n else 0.0,
    )
