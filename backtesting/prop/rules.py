"""
Prop firm account rules and constraint checking.

GFT defaults:
  - 25k 2-Step: daily DD ≤ 5% (~$1,233), max loss ≤ 10% (~$2,466),
                 phase 1 target 8%, phase 2 target 5%
  - 100k 1-Step: daily DD ≤ 4% (~$3,992), max loss ≤ 6% (~$5,988),
                  target 10%
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PropAccount:
    """One prop firm account definition."""

    name: str
    initial_equity: float
    daily_dd_pct: float          # max daily drawdown as decimal
    max_dd_pct: float             # max total drawdown as decimal
    target_pct: float             # profit target to pass
    position_step_lots: float = 0.01  # lot size increments (GFT: 0.01)

    @property
    def daily_dd_dollars(self) -> float:
        return round(self.initial_equity * self.daily_dd_pct, 2)

    @property
    def max_dd_dollars(self) -> float:
        return round(self.initial_equity * self.max_dd_pct, 2)

    @property
    def target_dollars(self) -> float:
        return round(self.initial_equity * self.target_pct, 2)

    def check_daily_dd(self, equity: float, day_start_equity: float) -> bool:
        """True if daily drawdown limit is breached."""
        if day_start_equity <= 0:
            return False
        dd = (day_start_equity - equity) / day_start_equity
        return dd > self.daily_dd_pct

    def check_max_dd(self, equity: float, peak_equity: float) -> bool:
        """True if max drawdown limit is breached."""
        if peak_equity <= 0:
            return False
        dd = (peak_equity - equity) / peak_equity
        return dd > self.max_dd_pct

    def check_target(self, equity: float) -> bool:
        """True if profit target has been reached."""
        return (equity - self.initial_equity) / self.initial_equity >= self.target_pct

    def __repr__(self) -> str:
        return (
            f"PropAccount({self.name}, ${self.initial_equity:,.0f}, "
            f"daily DD {self.daily_dd_pct:.1%}, max DD {self.max_dd_pct:.1%})"
        )


# ── Presets ───────────────────────────────────────────────────────────────────

GFT_25K_2STEP = PropAccount(
    name="GFT 25k 2-Step",
    initial_equity=25_000.0,
    daily_dd_pct=0.05,
    max_dd_pct=0.10,
    target_pct=0.08,  # phase 1; phase 2 = 0.05
)

GFT_100K_1STEP = PropAccount(
    name="GFT 100k 1-Step",
    initial_equity=100_000.0,
    daily_dd_pct=0.04,
    max_dd_pct=0.06,
    target_pct=0.10,
)

ACCOUNTS: dict[str, PropAccount] = {
    "GFT_25k_2STEP": GFT_25K_2STEP,
    "GFT_100k_1STEP": GFT_100K_1STEP,
}


def get_account(name: str) -> PropAccount:
    """Look up a prop account by name. Raises KeyError if unknown."""
    if name in ACCOUNTS:
        return ACCOUNTS[name]
    raise KeyError(f"Unknown account '{name}'. Available: {list(ACCOUNTS.keys())}")
