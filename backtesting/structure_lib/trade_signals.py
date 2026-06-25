"""
Step 3e — Trade Signal Generator.

Combine liquidity sweep + structure shift (CHoCH/BOS) + FVG/OB → entry signal.

The standard ICT trade sequence:
1. Identify liquidity pool (session high/low, prior day level, swing point)
2. Wait for sweep of that pool
3. Structure shift confirms reversal direction (CHoCH/BOS)
4. Displacement creates FVG or OB entry zone
5. Enter on retracement to FVG CE or OB zone
6. SL beyond sweep extreme
7. TP at opposite liquidity pool
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from backtesting.structure_lib.sweep import LiquidityPool, Sweep
from backtesting.structure_lib.fvg import FVG
from backtesting.structure_lib.ob import OrderBlock


@dataclass
class TradeSignal:
    direction: str  # "long" or "short"
    entry: float
    sl: float
    tp: float
    risk_pips: float
    reward_pips: float
    rr_ratio: float
    signal_time: pd.Timestamp
    pool: LiquidityPool
    sweep: Sweep
    fvg: Optional[FVG] = None
    ob: Optional[OrderBlock] = None
    confidence: str = "medium"  # "low", "medium", "high"

    def __repr__(self) -> str:
        return (
            f"  {self.direction.upper()} @ {self.entry:.5f} "
            f"| SL {self.sl:.5f} TP {self.tp:.5f} "
            f"| {self.risk_pips:.1f}p risk / {self.reward_pips:.1f}p reward "
            f"| 1:{self.rr_ratio:.1f} R:R"
            f"| {self.confidence}"
        )


def generate_signals(
    ohlc: pd.DataFrame,
    labels: pd.DataFrame,
    sweeps: list[Sweep],
    fvgs: list[FVG],
    obs: list[OrderBlock],
    pools: list[LiquidityPool],
    min_rr: float = 1.5,
) -> list[TradeSignal]:
    """
    Generate trade signals by combining sweep + CHoCH + FVG/OB.

    For each sweep:
    1. Check if a structure shift (CHoCH/BOS) occurred within N candles after the sweep
    2. Check if an FVG or OB exists near the displacement
    3. If yes, compute entry/SL/TP

    Parameters
    ----------
    ohlc : pd.DataFrame
        OHLC data with DatetimeIndex.
    labels : pd.DataFrame
        Structure labels from label_structure().
    sweeps : list of Sweep
        Detected liquidity sweeps.
    fvgs : list of FVG
        Detected fair value gaps.
    obs : list of OrderBlock
        Detected order blocks.
    pools : list of LiquidityPool
        Known liquidity pools (for TP determination).
    min_rr : float
        Minimum risk-reward ratio for a valid signal.

    Returns
    -------
    list of TradeSignal
    """
    signals: list[TradeSignal] = []

    for sweep in sweeps:
        if not sweep.reclaim and sweep.wick_only:
            continue  # Require at least a wick reclaim for lower confidence

        # Find a structure shift within 5 candles after the sweep
        shift_idx = None
        shift_direction = ""
        sweep_time = sweep.sweep_time

        for offset in range(6):  # 0 to 5 candles after sweep
            try:
                idx = ohlc.index.get_loc(sweep_time) + offset
            except (KeyError, IndexError):
                continue
            if idx >= len(labels):
                break

            row = labels.iloc[idx]

            if sweep.direction == "bullish" and (row["bullish_choch"] or row["bullish_bos"]):
                shift_idx = idx
                shift_direction = "bullish"
                break
            elif sweep.direction == "bearish" and (row["bearish_choch"] or row["bearish_bos"]):
                shift_idx = idx
                shift_direction = "bearish"
                break

        if shift_idx is None:
            continue  # No structure confirmation = no signal

        # Determine trade direction based on sweep type + shift
        # Swept sell-side (SSL) → bullish swing → LONG
        # Swept buy-side (BSL) → bearish swing → SHORT
        if shift_direction == "bullish":
            trade_dir = "long"
        else:
            trade_dir = "short"

        shift_time = ohlc.index[shift_idx]

        # Find FVG associated with this displacement
        matching_fvg = None
        for fvg in fvgs:
            if fvg.c2_time >= sweep_time and fvg.c2_time <= shift_time + pd.Timedelta(minutes=15):
                if (trade_dir == "long" and fvg.kind == "bullish") or \
                   (trade_dir == "short" and fvg.kind == "bearish"):
                    matching_fvg = fvg
                    break

        # Find OB associated with this displacement
        matching_ob = None
        for ob in obs:
            if ob.time >= sweep_time and ob.displacement_idx == shift_idx:
                if (trade_dir == "long" and ob.kind == "bullish") or \
                   (trade_dir == "short" and ob.kind == "bearish"):
                    matching_ob = ob
                    break

        if matching_fvg is None and matching_ob is None:
            continue  # No FVG or OB = no precise entry zone

        # Determine entry price
        entry = 0.0
        if matching_fvg:
            entry = matching_fvg.ce  # FVG midpoint (CE)
        elif matching_ob:
            # Entry at OB proximal edge (closest to current price)
            if trade_dir == "long":
                entry = matching_ob.top  # buy at top of OB
            else:
                entry = matching_ob.bottom  # sell at bottom of OB

        # Determine SL (beyond sweep level or FVG edge)
        if trade_dir == "long":
            # SL below the swept low (or below FVG bottom)
            sl = min(sweep.pool.level, matching_fvg.bottom if matching_fvg else entry)
            sl -= (ohlc["high"].iloc[shift_idx] - ohlc["low"].iloc[shift_idx]) * 0.3  # buffer
        else:
            # SL above the swept high (or above FVG top)
            sl = max(sweep.pool.level, matching_fvg.top if matching_fvg else entry)
            sl += (ohlc["high"].iloc[shift_idx] - ohlc["low"].iloc[shift_idx]) * 0.3

        # Determine TP (opposite liquidity pool)
        tp = _find_opposite_pool(pools, entry, trade_dir)

        if tp is None:
            continue  # No viable target

        # Calculate pips and R:R
        risk_abs = abs(entry - sl)
        reward_abs = abs(tp - entry)
        if risk_abs == 0:
            continue

        # Convert to pips (accounting for decimal places)
        risk_pips = risk_abs * 10000 if risk_abs < 1 else risk_abs
        reward_pips = reward_abs * 10000 if reward_abs < 1 else reward_abs
        rr = reward_abs / risk_abs

        if rr < min_rr:
            continue  # Skip bad R:R

        # Confidence level
        confidence = "medium"
        if matching_fvg and matching_ob:
            confidence = "high"
        elif "prior_day" in sweep.pool.source or "session" in sweep.pool.source:
            confidence = "high"
        elif matching_fvg:
            confidence = "high"

        signals.append(TradeSignal(
            direction=trade_dir,
            entry=entry,
            sl=sl,
            tp=tp,
            risk_pips=round(risk_pips, 1),
            reward_pips=round(reward_pips, 1),
            rr_ratio=round(rr, 1),
            signal_time=shift_time,
            pool=sweep.pool,
            sweep=sweep,
            fvg=matching_fvg,
            ob=matching_ob,
            confidence=confidence,
        ))

    # Deduplicate overlapping signals
    signals = _deduplicate_signals(signals)
    signals.sort(key=lambda s: s.signal_time)
    return signals


def _find_opposite_pool(
    pools: list[LiquidityPool],
    entry: float,
    direction: str,
) -> float | None:
    """Find the most logical TP target — a pool on the opposite side of entry."""
    if direction == "long":
        # Find the nearest buy-side pool above entry
        above = [p for p in pools if p.side == "buy" and p.level > entry]
        if not above:
            return None
        above.sort(key=lambda p: p.level)
        return above[0].level
    else:
        # Find the nearest sell-side pool below entry
        below = [p for p in pools if p.side == "sell" and p.level < entry]
        if not below:
            return None
        below.sort(key=lambda p: p.level, reverse=True)
        return below[0].level


def _deduplicate_signals(signals: list[TradeSignal]) -> list[TradeSignal]:
    """Remove overlapping signals for the same sweep pool."""
    unique: list[TradeSignal] = []
    seen_pools: set[float] = set()

    for s in signals:
        if s.pool.level not in seen_pools:
            seen_pools.add(s.pool.level)
            unique.append(s)

    return unique
