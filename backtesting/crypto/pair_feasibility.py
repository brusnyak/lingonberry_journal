"""
Pair feasibility for a given starting account size.

Why this exists: BTCUSDT's exchange min_notional is $50 -- exactly the
entire balance of a $50 starting account. At any sane risk_pct, the
ATR-based stop distance on a $65k asset produces a position size whose
notional is far below $50, so `CryptoCosts.calc_lots` returns 0 and the
strategy silently never trades it (found while running Phase 6A/6B
sweeps at $50 initial equity -- BTCUSDT produced zero trades across every
config while every other core pair traded fine).

This isn't a strategy problem or a bug -- it's a structural mismatch
between account size and instrument, and it will recur for every future
sweep run at small account sizes unless checked up front. This module is
a simple, one-purpose filter: given an account size and leverage, which
pairs are actually capable of opening a position at all (independent of
whether any strategy has edge on them).

Not a ranking/scoring tool (that's `screener.py`, which answers "which
pairs are worth trading" based on volatility/volume/behavior) -- this
answers the narrower, prerequisite question "can this account size even
place a minimum-sized trade on this pair."
"""
from __future__ import annotations

from dataclasses import dataclass

from backtesting.crypto.data import load_market_specs


@dataclass
class FeasibilityResult:
    pair: str
    feasible: bool
    min_notional: float
    buying_power: float
    notional_pct_of_buying_power: float  # min_notional / buying_power
    reason: str


def check_pair_feasibility(
    pair: str,
    exchange: str,
    equity: float,
    leverage: float,
    max_notional_pct: float = 0.1,
) -> FeasibilityResult:
    """Can this account size realistically trade this pair at all?

    `max_notional_pct`: the minimum-size position shouldn't eat more than
    this fraction of total buying power (equity * leverage), so there's
    room for the stop-driven position size to matter and for more than
    one trade's worth of margin to exist. Default 0.1 (10%) is
    deliberately conservative -- this is a rule-of-thumb GATE, not a
    precise predictor: the real position size a strategy computes
    (risk_pct * equity / stop_distance, per CryptoCosts.calc_lots) depends
    on the stop distance too, not just min_notional vs. buying power.
    Calibrated against the actual failure this module exists to catch:
    BTCUSDT's real min_notional ($50) is exactly 20% of a $50/5x account's
    buying power ($250) and STILL produced zero trades across every
    Phase 6A config -- so 20% was already too generous a cutoff. Treat
    this as a go/no-go gate before spending sweep time on a pair that
    structurally can't trade, not a guarantee either way.
    """
    specs = load_market_specs(pair, exchange)
    min_notional = specs.get("min_notional", 0.0)
    buying_power = equity * leverage

    if buying_power <= 0:
        return FeasibilityResult(pair, False, min_notional, buying_power, float("inf"),
                                  "invalid equity/leverage")
    if min_notional <= 0:
        # No spec on file -- can't rule it out, but can't confirm either.
        return FeasibilityResult(pair, True, min_notional, buying_power, 0.0,
                                  "no min_notional spec found, assuming feasible")

    pct = min_notional / buying_power
    if pct > max_notional_pct:
        return FeasibilityResult(
            pair, False, min_notional, buying_power, pct,
            f"min_notional ${min_notional:.2f} is {pct:.0%} of ${buying_power:.0f} "
            f"buying power (limit {max_notional_pct:.0%}) -- a single minimum-size "
            f"position would dominate the account",
        )
    return FeasibilityResult(pair, True, min_notional, buying_power, pct, "feasible")


def filter_feasible_pairs(
    pairs: list[str],
    exchange: str,
    equity: float,
    leverage: float,
    max_notional_pct: float = 0.1,
) -> tuple[list[str], list[FeasibilityResult]]:
    """Split a pair list into (feasible, all_results) for a given account.

    Use this to filter CORE_PAIRS/ALT_PAIRS before a sweep, instead of
    discovering mid-sweep that a pair silently produced zero trades.
    """
    results = [check_pair_feasibility(p, exchange, equity, leverage, max_notional_pct)
               for p in pairs]
    feasible = [r.pair for r in results if r.feasible]
    return feasible, results
