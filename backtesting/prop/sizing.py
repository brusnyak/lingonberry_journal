"""
Position sizing for prop firm accounts.

All sizes respect:
  - Account lot step (e.g. 0.01 for GFT)
  - Risk % per trade
  - Stop loss in pips
  - Pip value per lot
  - Daily DD budget (max risk per day)
"""

from __future__ import annotations

import math

from backtesting.prop.rules import PropAccount


def calc_lots(
    equity: float,
    risk_pct: float,
    stop_pips: float,
    pip_value_per_lot: float = 10.0,
    lot_step: float = 0.01,
) -> float:
    """
    Calculate position size in lots based on risk.

    Args:
        equity: current account equity
        risk_pct: fraction of equity to risk (decimal, e.g. 0.01 = 1%)
        stop_pips: stop loss distance in pips
        pip_value_per_lot: $ per pip per standard lot
        lot_step: minimum lot increment

    Returns:
        Position size in lots, rounded down to lot_step.
    """
    if stop_pips <= 0 or risk_pct <= 0 or equity <= 0:
        return 0.0

    risk_dollars = equity * risk_pct
    raw_lots = risk_dollars / (stop_pips * pip_value_per_lot)

    # Round down to lot step (never exceed risk budget)
    lots = math.floor(raw_lots / lot_step) * lot_step
    return max(lots, 0.0)


def max_risk_daily(
    account: PropAccount,
    day_start_equity: float,
) -> float:
    """
    Maximum dollar risk for a single day.

    Based on daily DD limit, conservatively capped at 1/2 of the limit
    to avoid single-day failure from a bad streak.
    """
    budget = account.daily_dd_dollars * 0.5  # use half the daily budget
    return round(budget, 2)


def max_risk_per_trade(
    account: PropAccount,
    current_equity: float,
    daily_budget_remaining: float,
) -> float:
    """
    Maximum dollar risk for a single trade.

    Capped by: remaining daily budget, or 1% of equity, whichever is smaller.
    """
    one_pct = current_equity * 0.01
    return min(daily_budget_remaining, one_pct)
