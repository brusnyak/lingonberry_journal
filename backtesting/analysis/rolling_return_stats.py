"""
Rolling-window return/drawdown distribution for uncapped-return accounts.

`rolling_pass_rate.py` answers "did this window hit the target before
breaching" — meaningless for accounts with `target_pct=None` (own capital,
no challenge to pass, just a risk cap and open-ended return). This answers
the question that actually matters for those accounts: "if I started on a
random day, what return and what drawdown would this window have produced,
and how often would it have breached the risk cap along the way?"

Same reuse pattern as rolling_pass_rate.py: post-processes a trades
DataFrame from `engine.runner.run(...).to_df()`, one full backtest sliced
into many overlapping windows, no separate backtest logic.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtesting.prop.rules import PropAccount


@dataclass
class RollingReturnResult:
    n_windows: int
    n_breached: int
    breach_rate: float
    median_return_pct: float
    mean_return_pct: float
    worst_return_pct: float
    best_return_pct: float
    median_max_dd_pct: float
    worst_max_dd_pct: float
    pct_windows_positive: float


def rolling_window_return_stats(
    trades: pd.DataFrame,
    account: PropAccount,
    window_days: int = 30,
    step_days: int = 1,
) -> RollingReturnResult:
    """
    trades: DataFrame with at least ['exit_time', 'pnl'], pnl computed at
            whatever position sizing the backtest actually used -- caller
            is responsible for having run it at account.initial_equity so
            $ pnl scales correctly (same convention as rolling_pass_rate).
    account: PropAccount, typically one with target_pct=None (CRYPTO_50 /
             CRYPTO_300) -- but works for any account, target is ignored.
    """
    empty = RollingReturnResult(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if trades.empty:
        return empty

    tr = trades.sort_values("exit_time").reset_index(drop=True)
    tr["exit_time"] = pd.to_datetime(tr["exit_time"])
    first_day = tr["exit_time"].min().normalize()
    last_day = tr["exit_time"].max().normalize()

    returns = []
    max_dds = []
    breaches = 0
    n = 0

    start = first_day
    while start + pd.Timedelta(days=window_days) <= last_day:
        end = start + pd.Timedelta(days=window_days)
        window_trades = tr[(tr["exit_time"] >= start) & (tr["exit_time"] < end)]
        n += 1

        equity = account.initial_equity
        peak = equity
        day_start_equity = equity
        cur_date = None
        max_dd = 0.0
        breached = False

        for _, t in window_trades.iterrows():
            d = t["exit_time"].normalize()
            if cur_date is None or d != cur_date:
                day_start_equity = equity
                cur_date = d
            equity += t["pnl"]
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak * 100 if peak > 0 else 0.0)
            if not breached and (account.check_daily_dd(equity, day_start_equity)
                                  or account.check_max_dd(equity, peak)):
                breached = True
                breaches += 1
                # Keep tracking equity/DD for the rest of the window even
                # after a breach -- a real challenge would stop you, but
                # for a live account we still want to know what the window
                # as a whole looked like.

        returns.append((equity / account.initial_equity - 1) * 100)
        max_dds.append(max_dd)
        start += pd.Timedelta(days=step_days)

    if n == 0:
        return empty

    returns_arr = np.array(returns)
    dd_arr = np.array(max_dds)
    return RollingReturnResult(
        n_windows=n,
        n_breached=breaches,
        breach_rate=round(breaches / n, 3),
        median_return_pct=round(float(np.median(returns_arr)), 3),
        mean_return_pct=round(float(np.mean(returns_arr)), 3),
        worst_return_pct=round(float(np.min(returns_arr)), 3),
        best_return_pct=round(float(np.max(returns_arr)), 3),
        median_max_dd_pct=round(float(np.median(dd_arr)), 3),
        worst_max_dd_pct=round(float(np.max(dd_arr)), 3),
        pct_windows_positive=round(float((returns_arr > 0).mean()), 3),
    )
