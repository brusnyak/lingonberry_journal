"""
Scaling engine for micro accounts ($20 → $100+).

Usage:
    from backtesting.engine.scaling import ScalingPlan, simulate

    plan = ScalingPlan(start_equity=20.0, target_equity=100.0,
                       wr=0.55, rr=1.5, freq_per_day=3, risk_pct=0.05)
    sim = simulate(plan)
    print(sim.summary())
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScalingPlan:
    """What a strategy needs to deliver to hit the target."""
    start_equity: float
    target_equity: float
    wr: float           # win rate (0.0-1.0)
    rr: float           # risk:reward ratio
    freq_per_day: float  # expected trades per day
    risk_pct: float     # % of equity risked per trade (0.0-1.0)
    max_drawdown_pct: float = 0.30
    trading_days: int = 20
    slippage_pct: float = 0.001   # 0.1% slippage on each leg

    @property
    def ev_per_trade(self) -> float:
        """Expected R multiple per trade."""
        return self.wr * self.rr - (1 - self.wr)

    @property
    def expected_daily_return_pct(self) -> float:
        """Expected daily return as fraction of equity."""
        r = self.freq_per_day * self.risk_pct * self.ev_per_trade
        return r

    def check_feasibility(self) -> list[str]:
        issues = []
        if self.expected_daily_return_pct <= 0:
            issues.append(f"Negative or zero expectancy: EV/trade={self.ev_per_trade:.2f}R")
        days_needed = math.log(self.target_equity / self.start_equity) / math.log(1 + self.expected_daily_return_pct)
        if days_needed > self.trading_days:
            issues.append(f"Need {days_needed:.0f} days (have {self.trading_days}) at {self.expected_daily_return_pct:.1%}/day")
        if self.risk_pct > 0.10:
            issues.append(f"High risk: {self.risk_pct:.1%} per trade — 3 losses = {((1-self.risk_pct)**3 - 1):.1%}")
        return issues


@dataclass
class SimulationPath:
    """One simulated path from start to target or ruin."""
    succeeded: bool
    days: int
    final_equity: float
    max_dd: float
    trades: int
    equity_curve: list[float] = field(default_factory=list)


def simulate(
    plan: ScalingPlan,
    n_paths: int = 1000,
    seed: Optional[int] = None,
) -> list[SimulationPath]:
    """
    Monte Carlo simulation of compounding paths.

    Each path:
    - Starts at plan.start_equity
    - Trades freq_per_day times per trading day
    - Each trade has WR chance of winning RR * risk_pct * equity
    - or (1-WR) chance of losing risk_pct * equity
    - Stops when equity >= target, <= 0, or trading_days exceeded
    """
    if seed is not None:
        random.seed(seed)

    results: list[SimulationPath] = []

    for _ in range(n_paths):
        eq = plan.start_equity
        peak = eq
        max_dd = 0.0
        curve = [eq]
        total_trades = 0

        for day in range(plan.trading_days):
            for _ in range(max(1, round(plan.freq_per_day))):
                total_trades += 1
                risk_amount = eq * plan.risk_pct
                slippage = risk_amount * plan.slippage_pct

                if random.random() < plan.wr:
                    eq += risk_amount * plan.rr - slippage
                else:
                    eq -= risk_amount + slippage

                if eq <= 0:
                    eq = 0
                    curve.append(eq)
                    break

                peak = max(peak, eq)
                dd = (peak - eq) / peak
                max_dd = max(max_dd, dd)
                curve.append(eq)

            if eq <= 0 or eq >= plan.target_equity:
                break

        results.append(SimulationPath(
            succeeded=eq >= plan.target_equity,
            days=min(day + 1, plan.trading_days),
            final_equity=round(eq, 2),
            max_dd=round(max_dd, 4),
            trades=total_trades,
            equity_curve=curve,
        ))

    return results


def summary(results: list[SimulationPath], plan: ScalingPlan) -> str:
    """Print simulation summary with probabilities."""
    n = len(results)
    succeeded = sum(1 for r in results if r.succeeded)
    pct = succeeded / n * 100
    avg_dd = sum(r.max_dd for r in results) / n
    avg_trades = sum(r.trades for r in results) / n
    blown = sum(1 for r in results if r.final_equity <= 0)

    # Equity percentiles
    equities = sorted(r.final_equity for r in results)
    p10 = equities[int(n * 0.1)]
    p50 = equities[int(n * 0.5)]
    p90 = equities[int(n * 0.9)]

    lines = [
        f"Scaling Plan: ${plan.start_equity:.0f} → ${plan.target_equity:.0f} in {plan.trading_days}d",
        f"  Strategy: WR={plan.wr:.0%}  RR={plan.rr:.1f}  {plan.freq_per_day:.1f} trades/day  "
        f"risk={plan.risk_pct:.1%}",
        f"  EV/trade: {plan.ev_per_trade:+.2f}R  Expected daily: {plan.expected_daily_return_pct:.1%}",
        "",
        f"  Success rate:  {pct:.0f}%  ({succeeded}/{n})",
        f"  Blowup rate:   {blown/n*100:.0f}%  ({blown}/{n})",
        f"  Avg drawdown:  {avg_dd:.1%}",
        f"  Avg trades:    {avg_trades:.0f}",
        "",
        f"  Final equity percentiles:",
        f"    10th:  ${p10:.2f}",
        f"    50th:  ${p50:.2f}",
        f"    90th:  ${p90:.2f}",
    ]

    issues = plan.check_feasibility()
    if issues:
        lines.append("")
        lines.append("  ⚠ Warnings:")
        for issue in issues:
            lines.append(f"    - {issue}")

    return "\n".join(lines)
