"""Separate position manager for dynamic SL management.

Rules (configurable):
  1. BE_ON_BOS_AGAINST: if BOS fires against the trade direction, move SL to entry.
  2. BE_AT_50PCT: if price reaches 50% of target, move SL to entry.
  3. (Future rules can be added here.)

These rules are applied inside a walk-forward loop (bar by bar) so that SL
adjustments affect all subsequent exit checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PositionManagerConfig:
    be_on_bos_against: bool = True
    be_at_50pct_target: bool = True
    be_at_75pct_target: bool = False
    trail_on_bos_with: float = 0.0
    label: str = "default"
    # "high_low" = trigger on bar high/low touching threshold
    # "close" = trigger only on bar close at/through threshold (stronger)
    trigger_mode: str = "high_low"


def walk_managed_outcome(
    bars: pd.DataFrame,
    entry_i: int,
    direction: str,
    sl: float,
    tp: float,
    horizon: int = 200,
    track_excursion: bool = False,
    structure: Optional[pd.DataFrame] = None,
    config: PositionManagerConfig | None = None,
) -> dict | None:
    """First-touch walk-forward with dynamic position management.

    Same base logic as walk_structural_outcome(), but also applies
    PositionManager rules on each bar:
      - BOS against position → SL to breakeven
      - 50% of target reached → SL to breakeven

    Parameters
    ----------
    bars : OHLCV DataFrame (entry timeframe, used for walk).
    entry_i : bar index of entry.
    direction : 'long' or 'short'.
    sl : initial stop loss price.
    tp : take profit price.
    horizon : max bars to hold.
    track_excursion : track MFE/MAE.
    structure : structure DataFrame (entry timeframe) with bos_up/bos_down columns.
    config : position manager rules.

    Returns same dict as walk_structural_outcome().
    """
    entry = float(bars["close"].iat[entry_i])
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    target_r = abs(tp - entry) / risk

    cfg = config or PositionManagerConfig()
    end_i = min(entry_i + horizon, len(bars) - 1)

    mfe = mae = 0.0
    r_multiple = 0.0  # expiry default
    hit = False
    be_moved = False  # has SL been moved to breakeven?
    half_target_triggered = False  # prevent repeated triggers

    # Current effective SL (starts at original, may move to entry)
    current_sl = sl

    for j in range(entry_i + 1, end_i + 1):
        hi = float(bars["high"].iat[j])
        lo = float(bars["low"].iat[j])
        cl = float(bars["close"].iat[j])

        # ── Position management: adjust SL before exit check ──
        if not be_moved:
            # Rule 1: BOS against position → BE
            if cfg.be_on_bos_against and structure is not None:
                if j < len(structure):
                    if direction == "long" and bool(structure["bos_down"].iat[j]):
                        current_sl = entry
                        be_moved = True
                    elif direction == "short" and bool(structure["bos_up"].iat[j]):
                        current_sl = entry
                        be_moved = True

            # Rule 2: 50% of target hit → BE
            if not be_moved and cfg.be_at_50pct_target and not half_target_triggered:
                half_target_r = 0.5 * target_r
                half_hit = False
                if direction == "long":
                    half_target_price = entry + risk * half_target_r
                    if cfg.trigger_mode == "close":
                        half_hit = cl >= half_target_price
                    else:
                        half_hit = hi >= half_target_price
                else:
                    half_target_price = entry - risk * half_target_r
                    if cfg.trigger_mode == "close":
                        half_hit = cl <= half_target_price
                    else:
                        half_hit = lo <= half_target_price
                if half_hit:
                    current_sl = entry
                    be_moved = True
                    half_target_triggered = True

        # ── Exit check (same as walk_structural_outcome) ──
        if direction == "long":
            hit_tp = hi >= tp
            hit_sl = lo <= current_sl
            if track_excursion:
                mfe = max(mfe, (hi - entry) / risk)
                mae = max(mae, (entry - lo) / risk)
        else:  # short
            hit_tp = lo <= tp
            hit_sl = hi >= current_sl
            if track_excursion:
                mfe = max(mfe, (entry - lo) / risk)
                mae = max(mae, (hi - entry) / risk)

        if hit_tp and hit_sl:
            # Same-bar ambiguity: both TP and SL triggered.
            # If SL was moved to breakeven (not original), the TP hit is
            # more meaningful — price reached target. Only penalize as
            # loss if the ORIGINAL SL was hit.
            if be_moved and current_sl == entry:
                r_multiple, hit = target_r, True
            else:
                r_multiple, hit = -1.0, False
            end_i = j
            break
        if hit_tp:
            r_multiple, hit = target_r, True
            end_i = j
            break
        if hit_sl:
            r_multiple, hit = -1.0, False
            end_i = j
            break

    result = {
        "r_multiple": r_multiple,
        "hit": hit,
        "risk_price": risk,
        "bars_to_exit": end_i - entry_i,
        "exit_reason": _exit_kind_from_r(r_multiple),
        "be_moved": be_moved,
    }
    if track_excursion:
        result["mfe_r"] = mfe
        result["mae_r"] = -mae
    return result


def _exit_kind_from_r(r_multiple: float) -> str:
    if r_multiple > 0:
        return "target"
    if r_multiple < 0:
        return "stop"
    return "expiry"


def compare_management(
    bars: pd.DataFrame,
    entry_idx: int,
    direction: str,
    sl: float,
    tp: float,
    horizon: int = 200,
    structure: pd.DataFrame | None = None,
) -> dict:
    """Compare managed vs unmanaged outcome for the same trade.

    Returns dict with both r_multiple values and the difference.
    """
    base = walk_managed_outcome(
        bars, entry_idx, direction, sl, tp,
        horizon=horizon, track_excursion=True,
        structure=structure,
        config=PositionManagerConfig(be_on_bos_against=False, be_at_50pct_target=False),
    )
    managed = walk_managed_outcome(
        bars, entry_idx, direction, sl, tp,
        horizon=horizon, track_excursion=True,
        structure=structure,
        config=PositionManagerConfig(be_on_bos_against=True, be_at_50pct_target=True),
    )
    return {
        "base_r": base["r_multiple"] if base else 0.0,
        "managed_r": managed["r_multiple"] if managed else 0.0,
        "base_mfe": base.get("mfe_r", np.nan) if base else np.nan,
        "managed_mfe": managed.get("mfe_r", np.nan) if managed else np.nan,
        "base_mae": base.get("mae_r", np.nan) if base else np.nan,
        "managed_mae": managed.get("mae_r", np.nan) if managed else np.nan,
        "be_moved": managed.get("be_moved", False) if managed else False,
    }
