"""
Data models: Signal, Position, ClosedTrade.

All values in price units (not pips). PnL in account currency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class ExitReason(str, Enum):
    SL = "sl"
    TP1 = "tp1"
    TP2 = "tp2"
    TP3 = "tp3"
    TRAIL = "trail"
    SIGNAL = "signal"   # strategy closed manually
    EOD = "eod"         # end-of-data flush


@dataclass
class Signal:
    """Entry signal emitted by strategy.next()."""
    direction: Direction
    entry: float           # limit/market price
    sl: float              # stop loss price
    tp1: float             # first take profit
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    risk_pct: float = 0.005
    # Partial close fractions at TP1/TP2 (rest is runner)
    tp1_frac: float = 0.5
    tp2_frac: float = 0.3
    # Trail: after TP1 hit, trail remaining on structure
    trail: bool = True
    label: str = ""        # debug tag


@dataclass
class Position:
    """Live position tracked by the runner."""
    id: int
    direction: Direction
    entry_price: float
    entry_time: object      # pd.Timestamp
    sl: float
    tp1: float
    tp2: Optional[float]
    tp3: Optional[float]
    lots: float
    risk_pct: float
    tp1_frac: float
    tp2_frac: float
    trail: bool

    label: str = ""

    # Mutable state
    lots_remaining: float = field(init=False)
    entry_commission: float = 0.0  # round-trip comm paid at entry; netted into trade.pnl
    tp1_hit: bool = False
    tp2_hit: bool = False
    be_moved: bool = False         # SL moved to breakeven
    trail_stop: Optional[float] = None

    def __post_init__(self):
        self.lots_remaining = self.lots

    @property
    def runner_frac(self) -> float:
        return max(0.0, 1.0 - self.tp1_frac - self.tp2_frac)


@dataclass
class ClosedTrade:
    """Completed trade with full attribution."""
    id: int
    direction: Direction
    entry_price: float
    entry_time: object
    exit_price: float
    exit_time: object
    exit_reason: ExitReason
    lots: float
    pnl: float          # in account currency, after costs
    r_multiple: float   # pnl / initial_risk
    label: str = ""
