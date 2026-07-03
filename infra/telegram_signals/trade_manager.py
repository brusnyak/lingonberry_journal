"""
Position management for copied signals -- deliberately stricter than the
channel's own stated rule.

Channel's rule: move stop to breakeven only once TP1 is FULLY hit.
Ours: move to breakeven at TP1 OR once price has covered 50% of the
distance to TP1, whichever comes first. This closes the gap where a trade
runs most of the way to TP1 and then reverses hard before tagging it --
under their rule that's a full loss; under ours it's flat.

Partial closes: 50% at TP1, 25% at TP2, remaining 25% at the final TP
(or 50% of what's left at each level beyond TP3), per the channel's own
stated principle -- that part of their rule is sound and kept as-is.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def partial_fractions(n_takes: int) -> list[float]:
    """50% / 25% / 25% for exactly 3 takes; 50%-of-remaining per level otherwise."""
    if n_takes <= 0:
        return []
    if n_takes == 1:
        return [1.0]
    if n_takes == 2:
        return [0.5, 0.5]
    if n_takes == 3:
        return [0.5, 0.25, 0.25]
    fracs, remaining = [], 1.0
    for i in range(n_takes - 1):
        fracs.append(remaining * 0.5)
        remaining *= 0.5
    fracs.append(remaining)
    return fracs


@dataclass
class ManagedResult:
    n_tp_hit: int
    hit_stop: bool
    breakeven_armed_by: str | None  # "tp1" | "50pct_progress" | None
    weighted_r: float
    bars_walked: int
    unresolved_frac: float


def simulate_managed_trade(
    klines: list,
    entry: float,
    stop: float,
    takes: list[float],
    direction: str,
    be_rule: str = "tp1_only",
    progress_frac: float = 0.5,
    hold_bars: int = 6,
) -> ManagedResult:
    """
    be_rule:
      "tp1_only"        -- channel's own rule: BE only once TP1 fully prints.
      "progress"        -- BE as soon as price touches progress_frac of the
                            way to TP1 (single touch, no confirmation).
      "progress_hold"   -- BE only once price has stayed at/beyond
                            progress_frac for `hold_bars` consecutive bars
                            (require the move to actually hold, not just tag).
    """
    risk = abs(entry - stop)
    fracs = partial_fractions(len(takes))
    progress_level = entry + progress_frac * (takes[0] - entry) if takes and direction == "LONG" else (
        entry - progress_frac * (entry - takes[0]) if takes else None
    )

    effective_stop = stop
    breakeven_armed_by = None
    tp_hits: list[int] = []
    hit_stop = False
    bars_walked = 0
    consec_held = 0

    for k in klines:
        bars_walked += 1
        hi, lo, close = float(k[2]), float(k[3]), float(k[4])

        # Arm breakeven BEFORE checking stop this bar, so a bar that both
        # reaches the trigger and reverses to old-stop still exits at
        # breakeven, not the original (worse) stop.
        if breakeven_armed_by is None and takes and be_rule != "tp1_only":
            if be_rule == "progress":
                progressed = (hi >= progress_level) if direction == "LONG" else (lo <= progress_level)
                if progressed:
                    breakeven_armed_by = "progress"
                    effective_stop = entry
            elif be_rule == "progress_hold":
                held = (close >= progress_level) if direction == "LONG" else (close <= progress_level)
                consec_held = consec_held + 1 if held else 0
                if consec_held >= hold_bars:
                    breakeven_armed_by = "progress_hold"
                    effective_stop = entry

        stop_hit = (lo <= effective_stop) if direction == "LONG" else (hi >= effective_stop)

        for i, tp in enumerate(takes):
            if i in tp_hits:
                continue
            touched = (hi >= tp) if direction == "LONG" else (lo <= tp)
            if touched:
                tp_hits.append(i)
                if i == 0 and breakeven_armed_by is None:
                    breakeven_armed_by = "tp1"
                    effective_stop = entry

        if stop_hit:
            hit_stop = True
            break
        if len(tp_hits) >= len(takes):
            break

    n_hit = len(tp_hits)
    used = sum(fracs[:n_hit])
    r_per_tp = [(takes[i] - entry) / risk if direction == "LONG" else (entry - takes[i]) / risk
                for i in range(n_hit)]
    weighted_r = sum(f * r for f, r in zip(fracs[:n_hit], r_per_tp))
    if hit_stop:
        r_stop = (effective_stop - entry) / risk if direction == "LONG" else (entry - effective_stop) / risk
        weighted_r += (1.0 - used) * r_stop
    open_frac = max(0.0, 1.0 - used - (1.0 if hit_stop else 0.0))

    return ManagedResult(
        n_tp_hit=n_hit, hit_stop=hit_stop, breakeven_armed_by=breakeven_armed_by,
        weighted_r=round(weighted_r, 3), bars_walked=bars_walked,
        unresolved_frac=round(open_frac, 2),
    )
