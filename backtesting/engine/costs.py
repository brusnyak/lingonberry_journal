"""
Cost models: ForexCosts, CryptoCosts.

ForexCosts — from PLAN.md:
  entry spread:  random uniform 1-3 pips
  exit spread:   random uniform 0.5-1.5 pips
  SL slippage:   random uniform 0-1 pip extra on stop hits
  commission:    $0.75 per side ($1.50 round-trip)
  min stop dist: >= 5 * avg_spread

CryptoCosts (Binance USDT-M futures):
  maker fee: 0.02%   taker fee: 0.04%
  funding:   from parquet file (ts, fundingRate), applied every 8h
  leverage:  configurable (default 10x)
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd


class CostModel(ABC):
    @abstractmethod
    def entry_fill(self, price: float, direction: str) -> float:
        """Return actual fill price after spread/slippage."""

    @abstractmethod
    def exit_fill(self, price: float, direction: str, is_sl: bool = False) -> float:
        """Return actual fill price on exit."""

    @abstractmethod
    def commission(self, lots: float, price: float) -> float:
        """Return total round-trip commission in account currency."""

    @abstractmethod
    def pip_value(self, lots: float, price: float = 1.0) -> float:
        """Value of 1 pip per lot in account currency."""

    def min_stop_pips(self) -> float:
        """Minimum stop distance in pips (0 = no minimum)."""
        return 0.0


# ── Forex ─────────────────────────────────────────────────────────────────────

@dataclass
class ForexCosts(CostModel):
    """
    Forex cost model matching PLAN.md spec.

    pip_size:     size of 1 pip in price units (0.0001 for most FX, 0.01 for JPY)
    pip_value_per_lot: account currency value of 1 pip on 1 standard lot
                       e.g. $10 for EURUSD with USD account
    commission_per_side: fixed per-side cost in account currency per standard lot
    """
    pip_size: float = 0.0001
    pip_value_per_lot: float = 10.0   # $10/pip/lot (standard EURUSD)
    commission_per_side: float = 0.75  # $0.75/side/lot

    def entry_fill(self, price: float, direction: str) -> float:
        spread = random.uniform(1.0, 3.0) * self.pip_size
        return price + spread if direction == "long" else price - spread

    def exit_fill(self, price: float, direction: str, is_sl: bool = False) -> float:
        spread = random.uniform(0.5, 1.5) * self.pip_size
        if is_sl:
            spread += random.uniform(0.0, 1.0) * self.pip_size  # extra slippage
        # On exit: spread works against you
        return price - spread if direction == "long" else price + spread

    def commission(self, lots: float, price: float = 1.0) -> float:
        return 2 * self.commission_per_side * lots  # round-trip

    def pip_value(self, lots: float, price: float = 1.0) -> float:
        return self.pip_value_per_lot * lots

    def min_stop_pips(self) -> float:
        return 5 * 2.0  # 5 × avg spread (avg = 2 pips)

    def pnl(self, entry: float, exit_: float, direction: str, lots: float) -> float:
        """PnL in account currency excluding commission."""
        price_move = exit_ - entry if direction == "long" else entry - exit_
        pips = price_move / self.pip_size
        return pips * self.pip_value(lots)

    def calc_lots(self, equity: float, risk_pct: float, stop_dist_price: float) -> float:
        """
        Size position so (lots × stop_dist_pips × pip_value) == equity × risk_pct.

        Returns lots rounded to 2 decimal places, minimum 0.01.
        """
        if stop_dist_price <= 0:
            return 0.01
        stop_pips = stop_dist_price / self.pip_size
        risk_amount = equity * risk_pct
        lots = risk_amount / (stop_pips * self.pip_value_per_lot)
        return max(0.01, round(lots, 2))


# ── Crypto ────────────────────────────────────────────────────────────────────

@dataclass
class CryptoCosts(CostModel):
    """
    Crypto futures cost model (Binance USDT-M / Bybit Linear).

    All fees as fractions (0.0004 = 0.04%).
    Leverage is used only for liquidation checks — not for position sizing.
    Position sizing is risk-based: risk_pct × equity / stop_dist_price.
    """
    maker_fee: float = 0.0002          # 0.02% Binance maker
    taker_fee: float = 0.0004          # 0.04% Binance taker
    leverage: float = 10.0
    pip_size: float = 1.0              # 1 price unit = 1 pip for linear perps
    funding_df: Optional[pd.DataFrame] = None  # columns: ts, fundingRate

    def entry_fill(self, price: float, direction: str) -> float:
        # Market entry = taker; limit = maker. Use taker by default.
        # Fill price is spot; fee applied separately via commission()
        return price

    def exit_fill(self, price: float, direction: str, is_sl: bool = False) -> float:
        # SL hits = market order (taker); TP limits = maker
        return price

    def commission(self, lots: float, price: float = 1.0) -> float:
        """Round-trip fee. lots = contracts (1 lot = 1 base unit)."""
        notional = lots * price
        return notional * (self.taker_fee + self.maker_fee)  # entry taker + exit maker

    def pip_value(self, lots: float, price: float = 1.0) -> float:
        # For crypto: PnL = contracts × price_move (linear perp)
        # "pip" is 1 USD move; pip_value = lots
        return lots

    def pnl(self, entry: float, exit_: float, direction: str, lots: float) -> float:
        price_move = exit_ - entry if direction == "long" else entry - exit_
        return price_move * lots

    def calc_lots(self, equity: float, risk_pct: float, stop_dist_price: float, price: float = 0.0) -> float:
        """
        Size so (lots × stop_dist_price) == equity × risk_pct,
        capped by available margin (equity × leverage / price).

        price: current asset price — required for margin cap.
        """
        if stop_dist_price <= 0:
            return 0.0
        risk_amount = equity * risk_pct
        lots_by_risk = risk_amount / stop_dist_price
        if price > 0:
            max_lots = (equity * self.leverage) / price
            lots_by_risk = min(lots_by_risk, max_lots)
        return max(0.0, lots_by_risk)

    def funding_cost(self, lots: float, price: float, open_time, close_time) -> float:
        """
        Apply funding rate charges between open_time and close_time.
        Funding periods: 00:00, 08:00, 16:00 UTC.
        Returns total funding cost (positive = you pay, negative = you receive).
        """
        if self.funding_df is None or self.funding_df.empty:
            return 0.0
        mask = (
            (self.funding_df["ts"] > open_time)
            & (self.funding_df["ts"] <= close_time)
        )
        rates = self.funding_df.loc[mask, "fundingRate"]
        if rates.empty:
            return 0.0
        notional = lots * price
        return float(rates.sum()) * notional  # positive rate = long pays short
