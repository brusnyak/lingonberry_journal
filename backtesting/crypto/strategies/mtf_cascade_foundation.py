"""MTF cascade foundation as a live-engine Strategy -- CAUSAL, no new mechanism.

Wraps the already-validated building blocks from mtf_cascade_direction.py
(global/local/mini direction cascade, structural SL/TP reused from
PropFirmStructureV1) into the standard engine.runner.run() interface, so the
foundation's edge can be measured as a *proper* backtest -- real trade-by-trade
equity curve, real CostModel (fees/funding/leverage), real max drawdown --
instead of the offline null-test harness's frictionless R-multiple walk.

This does not change the foundation logic. structure_ema_direction(),
ema_only_direction(), asof_direction(), build_structure_index(), and
structural_stop_target() are imported and called exactly as the offline tool
calls them (CLEAN.md Phase 27: never invent a second mechanism).

One addition beyond the offline tool: a horizon-bar time stop (should_close),
porting walk_structural_outcome's horizon=200 concept into live mechanics via
the engine's existing should_close hook. The offline tool treats horizon
expiry as a frictionless r_multiple=0 flat exit; here it closes at the actual
bar price through the real CostModel, which is more realistic, not less.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.crypto.mtf_cascade_direction import (
    asof_direction,
    ema_only_direction,
    structural_stop_target,
    structure_ema_direction,
)
from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.features.structure import StructureConfig, build_structure_index


class MtfCascadeFoundation(Strategy):
    """Global(240m)+local(30m)+mini(5m) direction cascade, structural SL/TP.

    data dict must have "240", "30", and the entry_tf ("5" by default) keys.
    """

    _signal_source = "init_precomputed"

    def __init__(
        self,
        risk_pct: float = 0.005,
        min_rr: float = 1.5,
        horizon_bars: int = 200,
        structure_left: int = 2,
        structure_right: int = 2,
        min_stop_pct: Optional[float] = 0.1,
    ):
        self.risk_pct = risk_pct
        self.min_rr = min_rr
        self.horizon_bars = horizon_bars
        self.structure_left = structure_left
        self.structure_right = structure_right
        # Same fragility TrIct already guards against (Phase 6E): a stop a
        # few cents from entry makes calc_lots size the position off a near-
        # zero risk denominator, so the leverage cap -- not the intended
        # risk_pct -- ends up sizing the trade, and the R-multiple computed
        # from that same tiny stop_dist blows up (-7601R observed on one
        # BTC trade with a 1-cent stop, Phase 28). The offline null-test
        # harness never saw this because it hardcodes -1R on any SL hit;
        # the real engine sizes real dollars off the real stop distance, so
        # it can't be skipped here. min_stop_pct=0.1 (10bps) is universal --
        # same threshold for every symbol, well below every pair's median
        # structural stop (0.14-0.41%, Phase 25/28) -- drops only the
        # degenerate tail, not real tight-but-legitimate stops.
        self.min_stop_pct = min_stop_pct

        self._combo: pd.Series = pd.Series(dtype=object)
        self._changed: pd.Series = pd.Series(dtype=bool)
        self._structure: pd.DataFrame = pd.DataFrame()
        self._ts: np.ndarray = np.array([])
        self._n = 0

    def init(self, data: dict[str, pd.DataFrame]) -> None:
        for tf in ("240", "30", "5"):
            if tf not in data:
                raise ValueError(f"MtfCascadeFoundation requires data['{tf}']")

        bars_global = data["240"].reset_index(drop=True)
        bars_local = data["30"].reset_index(drop=True)
        bars_mini = data["5"].reset_index(drop=True)

        dir_global = structure_ema_direction(bars_global, self.structure_left, self.structure_right)
        dir_local = structure_ema_direction(bars_local, self.structure_left, self.structure_right)
        dir_mini = ema_only_direction(bars_mini)

        g = asof_direction(bars_mini["ts"], dir_global)
        l = asof_direction(bars_mini["ts"], dir_local)
        m = dir_mini["direction"].to_numpy()
        combo = np.where((g == l) & (l == m) & (g != "neutral"), g, "neutral")

        self._combo = pd.Series(combo)
        self._changed = self._combo.ne(self._combo.shift(1)) & self._combo.isin(["bull", "bear"])
        self._structure = build_structure_index(bars_mini, StructureConfig(left=self.structure_left, right=self.structure_right))
        # Match dtype/tz-awareness of the raw ts column exactly as the engine
        # feeds it to BarData/Position (no forced UTC normalization here) --
        # otherwise should_close's searchsorted crashes comparing tz-naive
        # bar timestamps against a tz-aware index.
        self._ts = bars_mini["ts"].to_numpy()
        self._n = len(bars_mini)

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None
        i = bar.index
        if i >= self._n or not bool(self._changed.iat[i]):
            return None

        direction = "long" if self._combo.iat[i] == "bull" else "short"
        srow = self._structure.iloc[i]
        entry = bar.close
        sl, tp = structural_stop_target(srow, direction, entry, self.min_rr)
        if not np.isfinite(sl):
            return None
        if self.min_stop_pct is not None and (abs(entry - sl) / entry * 100) < self.min_stop_pct:
            return None

        return Signal(
            direction=Direction.LONG if direction == "long" else Direction.SHORT,
            entry=entry,
            sl=sl,
            tp1=tp,
            tp2=None,
            tp3=None,
            risk_pct=self.risk_pct,
            tp1_frac=1.0,
            tp2_frac=0.0,
            trail=False,
            label="mtf_cascade_foundation",
        )

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        """Horizon-bar time stop -- CLEAN.md Phase 17/27's horizon=200 concept,
        ported to live-engine mechanics (real exit price/costs instead of the
        offline tool's frictionless r=0 expiry)."""
        i = bar.index
        if i >= self._n:
            return False
        # No datetime64/tz normalization here -- self._ts and position.entry_time
        # both trace back to the exact same data["5"]["ts"] column (the engine
        # sets entry_time=bar.ts straight from that column), so they're always
        # mutually comparable as-is. Forcing a dtype conversion on one side but
        # not the other is what breaks this when ts is tz-aware.
        entry_idx = int(np.searchsorted(self._ts, position.entry_time))
        return (i - entry_idx) >= self.horizon_bars
