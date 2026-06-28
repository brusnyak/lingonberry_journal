"""PropFirmStructureV1 — structure-state candidate for GFT research.

This is a first candidate, not a live strategy. It tests whether a simple
state machine built from causal structure features can produce useful 30D
profiles before adding execution complexity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.features.structure import StructureConfig, build_structure_index


@dataclass
class _Thesis:
    direction: Direction
    sweep_i: int
    invalidation: float


class PropFirmStructureV1(Strategy):
    """Sweep -> structure break -> structural SL -> minimum-R target."""

    def __init__(
        self,
        risk_pct: float = 0.0025,
        min_rr: float = 1.5,
        max_mss_bars: int = 12,
        max_reentries_per_day: int = 1,
        left: int = 2,
        right: int = 2,
        direction: str = "both",
        require_htf: bool = True,
        htf_tf: str = "240",
        buffer_pips: float = 2.0,
        pip_size: float = 0.1,
        structure_cut: bool = True,
        sessions: tuple[str, ...] | list[str] | None = None,
    ):
        self.risk_pct = risk_pct
        self.min_rr = min_rr
        self.max_mss_bars = max_mss_bars
        self.max_reentries_per_day = max_reentries_per_day
        self.left = left
        self.right = right
        self.direction = direction
        self.require_htf = require_htf
        self.htf_tf = htf_tf
        self.buffer_pips = buffer_pips
        self.pip_size = pip_size
        self.structure_cut = structure_cut
        self.sessions = {s.strip().lower() for s in sessions or () if s and s.strip()}

    def init(self, data: dict[str, pd.DataFrame]) -> None:
        entry_key = next(iter(data))
        entry = data[entry_key].copy().sort_values("ts").reset_index(drop=True)
        self.entry = entry
        cfg = StructureConfig(left=self.left, right=self.right)
        st = build_structure_index(entry, cfg)

        if self.htf_tf in data:
            htf = build_structure_index(data[self.htf_tf].copy(), cfg)[["known_after_ts", "regime"]]
            htf = htf.rename(columns={"known_after_ts": "htf_known_after_ts", "regime": "htf_regime"})
            st = pd.merge_asof(
                st.sort_values("ts"),
                htf.sort_values("htf_known_after_ts"),
                left_on="ts",
                right_on="htf_known_after_ts",
                direction="backward",
            )
        else:
            st["htf_regime"] = "neutral"

        self.st = st.reset_index(drop=True)
        self.thesis: Optional[_Thesis] = None
        self.day_key = None
        self.entries_today = 0

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if i >= len(self.st):
            return None
        row = self.st.iloc[i]
        day = pd.Timestamp(bar.ts).date()
        if day != self.day_key:
            self.day_key = day
            self.entries_today = 0
            self.thesis = None

        if state.has_open_position:
            return None
        if self.entries_today >= self.max_reentries_per_day + 1:
            return None
        if self.sessions and _session_name(pd.Timestamp(bar.ts)) not in self.sessions:
            self.thesis = None
            return None

        htf = str(row.get("htf_regime") or "neutral")
        allow_long = self.direction in ("both", "long", "bull") and (not self.require_htf or htf in ("bull", "neutral"))
        allow_short = self.direction in ("both", "short", "bear") and (not self.require_htf or htf in ("bear", "neutral"))

        if allow_long and bool(row["sweep_low"]):
            inv = _first_finite(row.get("long_structural_sl"), row.get("last_swing_low"), bar.low)
            self.thesis = _Thesis(Direction.LONG, i, float(inv))
        elif allow_short and bool(row["sweep_high"]):
            inv = _first_finite(row.get("short_structural_sl"), row.get("last_swing_high"), bar.high)
            self.thesis = _Thesis(Direction.SHORT, i, float(inv))

        if self.thesis is None:
            return None
        if i - self.thesis.sweep_i > self.max_mss_bars:
            self.thesis = None
            return None

        if self.thesis.direction == Direction.LONG and not (bool(row["bos_up"]) or bool(row["choch_up"])):
            return None
        if self.thesis.direction == Direction.SHORT and not (bool(row["bos_down"]) or bool(row["choch_down"])):
            return None

        signal = self._build_signal(bar, row, self.thesis)
        self.thesis = None
        if signal is not None:
            self.entries_today += 1
        return signal

    def _build_signal(self, bar: BarData, row: pd.Series, thesis: _Thesis) -> Optional[Signal]:
        buf = self.buffer_pips * self.pip_size
        if thesis.direction == Direction.LONG:
            entry = float(bar.close)
            sl = min(float(thesis.invalidation) - buf, float(bar.low) - buf)
            risk = entry - sl
            if risk <= 0:
                return None
            target = _first_finite(row.get("long_target_1"), row.get("last_swing_high"), entry + self.min_rr * risk)
            tp = max(float(target), entry + self.min_rr * risk)
            return Signal(Direction.LONG, entry, sl, tp, risk_pct=self.risk_pct, tp1_frac=1.0, tp2_frac=0.0, trail=False, label="pf_struct_long")

        entry = float(bar.close)
        sl = max(float(thesis.invalidation) + buf, float(bar.high) + buf)
        risk = sl - entry
        if risk <= 0:
            return None
        target = _first_finite(row.get("short_target_1"), row.get("last_swing_low"), entry - self.min_rr * risk)
        tp = min(float(target), entry - self.min_rr * risk)
        return Signal(Direction.SHORT, entry, sl, tp, risk_pct=self.risk_pct, tp1_frac=1.0, tp2_frac=0.0, trail=False, label="pf_struct_short")

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        if not self.structure_cut or bar.index >= len(self.st):
            return False
        row = self.st.iloc[bar.index]
        if position.direction == Direction.LONG:
            return bool(row["choch_down"] or row["bos_down"] or row["sweep_high"])
        return bool(row["choch_up"] or row["bos_up"] or row["sweep_low"])


def _first_finite(*values) -> float:
    for value in values:
        try:
            f = float(value)
        except Exception:
            continue
        if np.isfinite(f):
            return f
    return float("nan")


def _session_name(ts: pd.Timestamp) -> str:
    hour = ts.hour
    if 7 <= hour < 10:
        return "london_open"
    if 13 <= hour < 16:
        return "ny_open"
    if 0 <= hour < 7:
        return "asia"
    return "other"
