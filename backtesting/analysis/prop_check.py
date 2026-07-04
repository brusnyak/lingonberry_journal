"""
Reusable prop-account compliance check on a trades DataFrame.

Extracted after being hand-rolled inline 3+ times in scratch scripts this
session (combined-book validation, per-account risk calibration checks).
Percentage-based dd/target rules from PropAccount are scale-invariant, so
this works whether the backtest ran at $10k or the account's real dollar
size -- pass `initial_equity` matching whatever baseline the trades'
`pnl` column was computed against.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backtesting.prop.rules import PropAccount


@dataclass
class PropCheckResult:
    n_trades: int
    final_equity: float
    return_pct: float
    max_dd_pct: float
    breached: bool
    breach_at: object  # pd.Timestamp or None
    breach_type: str | None  # "daily", "max", or None
    target_hit: bool


def check_prop_compliance(trades: pd.DataFrame, account: PropAccount,
                           initial_equity: float = 10_000.0) -> PropCheckResult:
    if trades is None or len(trades) == 0:
        return PropCheckResult(0, initial_equity, 0.0, 0.0, False, None, None, False)

    tr = trades.sort_values("entry_time")
    equity = initial_equity
    peak = equity
    day_start = equity
    cur_day = None
    max_dd = 0.0
    breached = False
    breach_at = None
    breach_type = None

    for _, t in tr.iterrows():
        d = pd.Timestamp(t["entry_time"]).date()
        if d != cur_day:
            day_start = equity
            cur_day = d
        equity += t["pnl"]
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100 if peak > 0 else 0.0)
        if not breached:
            if account.check_daily_dd(equity, day_start):
                breached, breach_at, breach_type = True, t["entry_time"], "daily"
                break
            if account.check_max_dd(equity, peak):
                breached, breach_at, breach_type = True, t["entry_time"], "max"
                break

    target_hit = (equity - initial_equity) / initial_equity >= account.target_pct
    return PropCheckResult(
        n_trades=len(tr), final_equity=equity,
        return_pct=(equity / initial_equity - 1) * 100,
        max_dd_pct=max_dd, breached=breached, breach_at=breach_at,
        breach_type=breach_type, target_hit=target_hit,
    )
