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
  leverage:  configurable (default 50x for challenge simulation)
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import floor
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
    seed: Optional[int] = None           # spread/slippage RNG seed; None = OS entropy (non-reproducible)
    fixed_spread_pips: Optional[float] = None  # if set, use flat spread instead of random uniform

    def __post_init__(self):
        # Private RNG so two ForexCosts instances (and re-runs) are bit-for-bit
        # reproducible. A backtest you can't reproduce you can't debug.
        self._rng = random.Random(self.seed) if self.seed is not None else random.Random()

    def _spread_pips(self) -> float:
        if self.fixed_spread_pips is not None:
            return self.fixed_spread_pips
        return self._rng.uniform(1.0, 3.0)

    def _exit_spread_pips(self) -> float:
        if self.fixed_spread_pips is not None:
            return self.fixed_spread_pips
        return self._rng.uniform(0.5, 1.5)

    def _slip_pips(self) -> float:
        if self.fixed_spread_pips is not None:
            return 0.0  # no extra slip when spread is fixed
        return self._rng.uniform(0.0, 1.0)

    def entry_fill(self, price: float, direction: str) -> float:
        spread = self._spread_pips() * self.pip_size
        return price + spread if direction == "long" else price - spread

    def exit_fill(self, price: float, direction: str, is_sl: bool = False) -> float:
        spread = self._exit_spread_pips() * self.pip_size
        if is_sl:
            spread += self._slip_pips() * self.pip_size  # extra slippage
        # On exit: spread works against you
        return price - spread if direction == "long" else price + spread

    def commission(self, lots: float, price: float = 1.0) -> float:
        return 2 * self.commission_per_side * lots  # round-trip

    def pip_value(self, lots: float, price: float = 1.0) -> float:
        return self.pip_value_per_lot * lots

    def min_stop_pips(self) -> float:
        # Avg spread = midpoint of entry_fill uniform(1.0, 3.0) = 2.0 pips
        avg_spread = (1.0 + 3.0) / 2.0
        return 5.0 * avg_spread

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
    Leverage caps position sizing and exposes liquidation checks.
    Position sizing is risk-based: risk_pct × equity / stop_dist_price.
    """
    maker_fee: float = 0.0002          # 0.02% Binance maker
    taker_fee: float = 0.0004          # 0.04% Binance taker
    leverage: float = 50.0
    pip_size: float = 1.0              # 1 price unit = 1 pip for linear perps
    funding_df: Optional[pd.DataFrame] = None  # columns: ts, fundingRate
    qty_step: float = 0.0              # exchange contract/base-qty step
    min_qty: float = 0.0
    min_notional: float = 0.0
    tick_size: float = 0.0
    maintenance_margin_rate: float = 0.005

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

    def entry_commission(self, lots: float, price: float) -> float:
        """Entry fee for market/taker entries."""
        return lots * price * self.taker_fee

    def exit_commission(self, lots: float, price: float, is_sl: bool = False) -> float:
        """Exit fee: stops are taker, targets are assumed maker."""
        fee = self.taker_fee if is_sl else self.maker_fee
        return lots * price * fee

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
            if self.min_notional > 0 and lots_by_risk * price < self.min_notional:
                return 0.0

        lots = max(0.0, lots_by_risk)
        if self.qty_step > 0:
            lots = floor(lots / self.qty_step) * self.qty_step
        if self.min_qty > 0 and lots < self.min_qty:
            return 0.0
        return lots

    def funding_cost(self, lots: float, price: float, open_time, close_time, direction: str = "long") -> float:
        """
        Apply funding rate charges between open_time and close_time.
        Funding periods: 00:00, 08:00, 16:00 UTC.
        Returns total funding cost (positive = trader pays, negative = trader receives).
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
        signed_rate = float(rates.sum())
        if direction == "short":
            signed_rate *= -1
        return signed_rate * notional  # positive funding: long pays short

    def liquidation_price(self, entry: float, direction: str) -> float:
        """
        Approximate isolated-margin liquidation threshold for linear perps.

        This is deliberately conservative for research. Real exchange formulas
        include bracketed maintenance rates, fees, wallet balance, and funding.
        """
        if self.leverage <= 0:
            return 0.0
        buffer = max(0.0, (1.0 / self.leverage) - self.maintenance_margin_rate)
        if direction == "long":
            return entry * (1.0 - buffer)
        return entry * (1.0 + buffer)

    def would_liquidate(self, entry: float, direction: str, bar_high: float, bar_low: float) -> bool:
        liq = self.liquidation_price(entry, direction)
        if direction == "long":
            return bar_low <= liq
        return bar_high >= liq
