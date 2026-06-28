"""Prop-firm account rule evaluation for backtest trades."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class PropAccountRules:
    name: str
    initial_balance: float
    target_pct: float
    daily_loss_pct: float
    max_loss_pct: float
    min_trading_days: int = 3

    @property
    def daily_loss_amount(self) -> float:
        return self.initial_balance * self.daily_loss_pct

    @property
    def max_loss_amount(self) -> float:
        return self.initial_balance * self.max_loss_pct


GFT_25K_GOAT_PHASE1 = PropAccountRules("GFT 25k GOAT Phase 1", 25_000.0, 0.08, 0.04, 0.10)
GFT_25K_GOAT_PHASE2 = PropAccountRules("GFT 25k GOAT Phase 2", 25_000.0, 0.06, 0.04, 0.10)
GFT_100K_1STEP = PropAccountRules("GFT 100k 1-Step", 100_000.0, 0.10, 0.04, 0.06)
GFT_RULESETS = [GFT_25K_GOAT_PHASE1, GFT_25K_GOAT_PHASE2, GFT_100K_1STEP]


def evaluate_prop_rules(
    trades: pd.DataFrame,
    rules: PropAccountRules,
    source_initial_balance: float | None = None,
) -> dict:
    """Evaluate a closed-trade DataFrame against one prop account ruleset."""
    if trades.empty:
        return _empty_result(rules)

    df = trades.copy()
    if "exit_time" not in df.columns or "pnl" not in df.columns:
        raise ValueError("trades must include exit_time and pnl columns")
    df["exit_time"] = pd.to_datetime(df["exit_time"], utc=True)
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0)
    if source_initial_balance and source_initial_balance > 0:
        df["pnl"] *= rules.initial_balance / source_initial_balance
    df = df.sort_values("exit_time").reset_index(drop=True)

    equity = rules.initial_balance + df["pnl"].cumsum()
    peak = equity.cummax()
    drawdown = peak - equity
    max_dd_amount = float(drawdown.max()) if not drawdown.empty else 0.0
    max_dd_pct = max_dd_amount / rules.initial_balance if rules.initial_balance else 0.0

    daily = df.groupby(df["exit_time"].dt.date)["pnl"].sum().sort_index()
    max_daily_loss_amount = float(max(0.0, -daily.min())) if not daily.empty else 0.0
    max_daily_loss_pct = max_daily_loss_amount / rules.initial_balance if rules.initial_balance else 0.0
    trading_days = int((daily != 0).sum())

    total_pnl = float(df["pnl"].sum())
    return_pct = total_pnl / rules.initial_balance if rules.initial_balance else 0.0
    final_equity = rules.initial_balance + total_pnl
    min_equity = float(equity.min()) if not equity.empty else rules.initial_balance

    target_hit = return_pct >= rules.target_pct
    daily_breached = max_daily_loss_amount > rules.daily_loss_amount
    max_loss_breached = (rules.initial_balance - min_equity) > rules.max_loss_amount
    min_days_ok = trading_days >= rules.min_trading_days

    return {
        "ruleset": rules.name,
        "initial_balance": rules.initial_balance,
        "target_pct": rules.target_pct * 100.0,
        "return_pct": return_pct * 100.0,
        "target_hit": bool(target_hit),
        "final_equity": final_equity,
        "min_equity": min_equity,
        "max_dd_pct": max_dd_pct * 100.0,
        "max_daily_loss_pct": max_daily_loss_pct * 100.0,
        "daily_loss_limit_pct": rules.daily_loss_pct * 100.0,
        "max_loss_limit_pct": rules.max_loss_pct * 100.0,
        "daily_loss_breached": bool(daily_breached),
        "max_loss_breached": bool(max_loss_breached),
        "trading_days": trading_days,
        "min_trading_days": rules.min_trading_days,
        "min_days_ok": bool(min_days_ok),
        "passed": bool(target_hit and not daily_breached and not max_loss_breached and min_days_ok),
    }


def evaluate_all_gft_rules(
    trades: pd.DataFrame,
    rulesets: Iterable[PropAccountRules] = GFT_RULESETS,
    source_initial_balance: float | None = None,
) -> pd.DataFrame:
    return pd.DataFrame([evaluate_prop_rules(trades, rules, source_initial_balance) for rules in rulesets])


def _empty_result(rules: PropAccountRules) -> dict:
    return {
        "ruleset": rules.name,
        "initial_balance": rules.initial_balance,
        "target_pct": rules.target_pct * 100.0,
        "return_pct": 0.0,
        "target_hit": False,
        "final_equity": rules.initial_balance,
        "min_equity": rules.initial_balance,
        "max_dd_pct": 0.0,
        "max_daily_loss_pct": 0.0,
        "daily_loss_limit_pct": rules.daily_loss_pct * 100.0,
        "max_loss_limit_pct": rules.max_loss_pct * 100.0,
        "daily_loss_breached": False,
        "max_loss_breached": False,
        "trading_days": 0,
        "min_trading_days": rules.min_trading_days,
        "min_days_ok": False,
        "passed": False,
    }
