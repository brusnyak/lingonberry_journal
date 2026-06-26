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

import bisect
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
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

    Pre-indexes FVGs and OBs by time for O(log N) lookup per sweep.
    """
    # ── Pre-index FVGs by c2_time for binary search ──
    fvgs_sorted = sorted(fvgs, key=lambda f: f.c2_time) if fvgs else []
    fvg_times = [f.c2_time for f in fvgs_sorted]

    # ── Pre-index OBs by time ──
    obs_sorted = sorted(obs, key=lambda o: o.time) if obs else []
    ob_times = [o.time for o in obs_sorted]

    # ── Pre-sort pools by level for O(log N) opposite pool lookup ──
    buy_pools_sorted = sorted([p for p in pools if p.side == "buy"], key=lambda p: p.level)
    sell_pools_sorted = sorted([p for p in pools if p.side == "sell"], key=lambda p: p.level)
    buy_levels = [p.level for p in buy_pools_sorted]
    sell_levels = [p.level for p in sell_pools_sorted]

    # ── Pre-extract label arrays for fast access ──
    bullish_choch = labels["bullish_choch"].to_numpy(bool)
    bearish_choch = labels["bearish_choch"].to_numpy(bool)
    bullish_bos = labels["bullish_bos"].to_numpy(bool)
    bearish_bos = labels["bearish_bos"].to_numpy(bool)

    signals: list[TradeSignal] = []

    for sweep in sweeps:
        if not sweep.reclaim and sweep.wick_only:
            continue

        # Find structure shift within 5 candles after sweep (binary search index)
        try:
            sweep_idx = ohlc.index.get_loc(sweep.sweep_time)
        except KeyError:
            continue

        shift_idx = -1
        shift_direction = ""
        max_idx = min(sweep_idx + 6, len(labels))
        for idx in range(sweep_idx, max_idx):
            if sweep.direction == "bullish":
                if bullish_choch[idx] or bullish_bos[idx]:
                    shift_idx = idx
                    shift_direction = "bullish"
                    break
            else:
                if bearish_choch[idx] or bearish_bos[idx]:
                    shift_idx = idx
                    shift_direction = "bearish"
                    break

        if shift_idx < 0:
            continue

        trade_dir = "long" if shift_direction == "bullish" else "short"
        shift_time = ohlc.index[shift_idx]

        # ── Find matching FVG via binary search ──
        matching_fvg = None
        if fvg_times:
            sweep_ts = sweep.sweep_time
            shift_plus_15 = shift_time + pd.Timedelta(minutes=15)
            left = bisect.bisect_left(fvg_times, sweep_ts)
            right = bisect.bisect_right(fvg_times, shift_plus_15)
            for i in range(left, min(right, len(fvgs_sorted))):
                fvg = fvgs_sorted[i]
                if (trade_dir == "long" and fvg.kind == "bullish") or \
                   (trade_dir == "short" and fvg.kind == "bearish"):
                    matching_fvg = fvg
                    break

        # ── Find matching OB via binary search ──
        matching_ob = None
        if ob_times:
            sweep_ts = sweep.sweep_time
            left = bisect.bisect_left(ob_times, sweep_ts)
            for i in range(left, len(obs_sorted)):
                ob = obs_sorted[i]
                if ob.displacement_idx == shift_idx:
                    if (trade_dir == "long" and ob.kind == "bullish") or \
                       (trade_dir == "short" and ob.kind == "bearish"):
                        matching_ob = ob
                        break

        if matching_fvg is None and matching_ob is None:
            continue

        # ── Entry price ──
        if matching_fvg:
            entry = matching_fvg.ce
        else:
            entry = matching_ob.top if trade_dir == "long" else matching_ob.bottom

        # ── SL (beyond sweep level with buffer) ──
        shift_range = (ohlc["high"].iloc[shift_idx] - ohlc["low"].iloc[shift_idx]) * 0.3
        if trade_dir == "long":
            sl = min(sweep.pool.level, matching_fvg.bottom if matching_fvg else entry) - shift_range
        else:
            sl = max(sweep.pool.level, matching_fvg.top if matching_fvg else entry) + shift_range

        # ── TP via binary search on opposite pool ──
        tp = None
        if trade_dir == "long":
            idx = bisect.bisect_right(buy_levels, entry)
            if idx < len(buy_levels):
                tp = buy_levels[idx]
        else:
            idx = bisect.bisect_left(sell_levels, entry) - 1
            if idx >= 0:
                tp = sell_levels[idx]

        if tp is None:
            continue

        # ── R:R check ──
        risk_abs = abs(entry - sl)
        reward_abs = abs(tp - entry)
        if risk_abs == 0:
            continue
        rr = reward_abs / risk_abs
        if rr < min_rr:
            continue

        # ── Pips for human readability ──
        risk_pips = risk_abs * 10000 if risk_abs < 1 else risk_abs
        reward_pips = reward_abs * 10000 if reward_abs < 1 else reward_abs

        # ── Confidence ──
        confidence = "medium"
        if matching_fvg and matching_ob:
            confidence = "high"
        elif "prior_day" in sweep.pool.source or "session" in sweep.pool.source:
            confidence = "high"
        elif matching_fvg:
            confidence = "high"

        signals.append(TradeSignal(
            direction=trade_dir, entry=entry, sl=sl, tp=tp,
            risk_pips=round(risk_pips, 1), reward_pips=round(reward_pips, 1),
            rr_ratio=round(rr, 1), signal_time=shift_time,
            pool=sweep.pool, sweep=sweep,
            fvg=matching_fvg, ob=matching_ob, confidence=confidence,
        ))

    # Deduplicate
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
    """Remove overlapping signals with same entry+dir within 1h."""
    unique: list[TradeSignal] = []
    seen: set[tuple[float, str, pd.Timestamp]] = set()

    for s in signals:
        bucket_h = s.signal_time.floor("h")
        key = (round(s.entry, 5), s.direction, bucket_h)
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return unique
