"""
SMC v1 — ICT sweep + FVG entry on GBPUSD.

Setup (bullish):
  1. In London (07:00–10:00 UTC) or NY (13:30–16:00 UTC) killzone
  2. Last confirmed 15m swing low (causal, no look-ahead) is taken out by a 1m wick
  3. Same 1m bar closes back above the swept level (wick sweep = bullish)
  4. A bullish FVG forms on 1m within fvg_max_bars after the sweep
  5. Price retraces into the FVG (1m low <= fvg.top)

Entry: bar.close (market), clipped to FVG zone
SL: sweep_low - pip_buffer pips
TP1: entry + tp1_r × risk  (50% close, SL → BE)
TP2: entry + tp2_r × risk  (30% close)
Runner: trailing stop on remaining 20%

Bearish setup is the mirror: 15m swing high sweep → bearish FVG → short.

Data required: {"1": df_1m, "15": df_15m}
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.structure_lib.fvg import FVG, detect_fvgs
from backtesting.structure_lib.swing import swing_points


class SmcV1(Strategy):
    def __init__(
        self,
        swing_length_15m: int = 3,
        killzone_filter: bool = True,
        fvg_max_bars: int = 30,
        tp1_r: float = 1.0,
        tp2_r: float = 1.5,
        risk_pct: float = 0.005,
        pip_buffer: int = 2,
        entry_tf_key: str = "1",   # key in data dict for FVG + entry bars
    ):
        self.swing_length_15m = swing_length_15m
        self.killzone_filter = killzone_filter
        self.fvg_max_bars = fvg_max_bars
        self.tp1_r = tp1_r
        self.tp2_r = tp2_r
        self.risk_pct = risk_pct
        self.pip_buffer = pip_buffer
        self.entry_tf_key = entry_tf_key

    # ── init ──────────────────────────────────────────────────────────────────

    def init(self, data: dict) -> None:
        df15 = data["15"].copy()
        if "ts" in df15.columns:
            df15 = df15.set_index("ts")
        df15.sort_index(inplace=True)

        df1 = data[self.entry_tf_key].copy()
        if "ts" in df1.columns:
            df1 = df1.set_index("ts")
        df1.sort_index(inplace=True)

        # Causal 15m swings (labeled swing_length bars after confirmation)
        sw15, lv15 = swing_points(df15, swing_length=self.swing_length_15m)
        self._sw15 = sw15
        self._lv15 = lv15

        # Pre-compute FVGs on entry TF; key by c3_idx (integer bar position)
        df1_reset = df1.reset_index()
        all_fvgs = detect_fvgs(df1_reset)
        # Most recently formed FVG wins if multiple share c3_idx (shouldn't happen)
        self._fvgs_by_c3: dict[int, FVG] = {}
        for f in all_fvgs:
            self._fvgs_by_c3[f.c3_idx] = f

        # Sliding window of recently confirmed 15m swings: [(ts, type, level)]
        # type: 1=high, -1=low
        self._recent_swings: list[tuple] = []

        # Active setup state
        self._dir: Optional[str] = None    # "bullish" / "bearish"
        self._sweep_level: float = 0.0     # swept 15m swing level
        self._sweep_bar_low: float = 0.0   # sweep bar low (for SL on bullish)
        self._sweep_bar_high: float = 0.0  # sweep bar high (for SL on bearish)
        self._sweep_bar_idx: int = -1
        self._mss_target: float = 0.0      # price level that confirms MSS
        self._mss_confirmed: bool = False
        self._pending_fvg: Optional[FVG] = None

        # Track last 15m period processed (to avoid duplicate updates)
        self._last_15m_ts: Optional[pd.Timestamp] = None

    # ── helpers ───────────────────────────────────────────────────────────────

    def _is_killzone(self, ts: pd.Timestamp) -> bool:
        if not self.killzone_filter:
            return True
        h, m = ts.hour, ts.minute
        london = 7 <= h < 10
        ny = (h == 13 and m >= 30) or (14 <= h < 16)
        return london or ny

    def _pump_15m(self, bar_ts: pd.Timestamp) -> None:
        """At the start of a new 15m bar, register any swing just confirmed."""
        ts_15m = bar_ts.floor("15min")
        if ts_15m == self._last_15m_ts:
            return
        self._last_15m_ts = ts_15m

        # The 15m bar that just closed is ts_15m - 15min
        prev_ts = ts_15m - pd.Timedelta(minutes=15)
        if prev_ts in self._sw15.index and not pd.isna(self._sw15[prev_ts]):
            sw_type = int(self._sw15[prev_ts])
            level = float(self._lv15[prev_ts])
            self._recent_swings.append((prev_ts, sw_type, level))
            if len(self._recent_swings) > 20:
                self._recent_swings.pop(0)

    def _last_swing_level(self, sw_type: int) -> Optional[float]:
        for _, t, level in reversed(self._recent_swings):
            if t == sw_type:
                return level
        return None

    def _reset(self) -> None:
        self._dir = None
        self._sweep_level = 0.0
        self._sweep_bar_low = 0.0
        self._sweep_bar_high = 0.0
        self._sweep_bar_idx = -1
        self._mss_target = 0.0
        self._mss_confirmed = False
        self._pending_fvg = None

    # ── next ──────────────────────────────────────────────────────────────────

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        bar_ts = pd.Timestamp(bar.ts)
        bar_idx = bar.index
        pip = 0.0001

        # Advance 15m swing state
        self._pump_15m(bar_ts)

        # ── 1. Expire setup on timeout ────────────────────────────────────────
        if self._dir is not None:
            if bar_idx - self._sweep_bar_idx > self.fvg_max_bars:
                self._reset()

        # ── 2. FVG entry ──────────────────────────────────────────────────────
        if self._pending_fvg is not None:
            fvg = self._pending_fvg
            if fvg.kind == "bullish" and bar.low <= fvg.top:
                entry = min(bar.close, fvg.top)
                # SL: below sweep bar low (tighter than sweep level, sensible structure)
                sl = self._sweep_bar_low - self.pip_buffer * pip
                stop = entry - sl
                if stop > 0:
                    self._reset()
                    return Signal(
                        direction=Direction.LONG,
                        entry=entry,
                        sl=sl,
                        tp1=entry + self.tp1_r * stop,
                        tp2=entry + self.tp2_r * stop,
                        risk_pct=self.risk_pct,
                        tp1_frac=0.5,
                        tp2_frac=0.3,
                        trail=True,
                        label="bull_sweep_fvg",
                    )

            elif fvg.kind == "bearish" and bar.high >= fvg.bottom:
                entry = max(bar.close, fvg.bottom)
                # SL: above sweep bar high
                sl = self._sweep_bar_high + self.pip_buffer * pip
                stop = sl - entry
                if stop > 0:
                    self._reset()
                    return Signal(
                        direction=Direction.SHORT,
                        entry=entry,
                        sl=sl,
                        tp1=entry - self.tp1_r * stop,
                        tp2=entry - self.tp2_r * stop,
                        risk_pct=self.risk_pct,
                        tp1_frac=0.5,
                        tp2_frac=0.3,
                        trail=True,
                        label="bear_sweep_fvg",
                    )

        # ── 3. Sweep detection ────────────────────────────────────────────────
        if self._dir is None and self._is_killzone(bar_ts):
            ssl = self._last_swing_level(-1)   # last 15m swing low
            bsl = self._last_swing_level(1)    # last 15m swing high

            if ssl is not None and bar.low < ssl and bar.close > ssl:
                self._dir = "bullish"
                self._sweep_level = ssl
                self._sweep_bar_low = bar.low    # SL goes below this
                self._sweep_bar_high = bar.high
                self._sweep_bar_idx = bar_idx
                # MSS: close above the HIGH of this sweep bar
                self._mss_target = bar.high
                self._mss_confirmed = False

            elif bsl is not None and bar.high > bsl and bar.close < bsl:
                self._dir = "bearish"
                self._sweep_level = bsl
                self._sweep_bar_low = bar.low
                self._sweep_bar_high = bar.high  # SL goes above this
                self._sweep_bar_idx = bar_idx
                # MSS: close below the LOW of this sweep bar
                self._mss_target = bar.low
                self._mss_confirmed = False

        # ── 4. MSS confirmation ───────────────────────────────────────────────
        if self._dir is not None and not self._mss_confirmed:
            if self._dir == "bullish" and bar.close > self._mss_target:
                self._mss_confirmed = True
            elif self._dir == "bearish" and bar.close < self._mss_target:
                self._mss_confirmed = True

        # ── 5. FVG registration after MSS ─────────────────────────────────────
        if self._dir is not None and self._mss_confirmed and self._pending_fvg is None:
            if bar_idx in self._fvgs_by_c3:
                fvg = self._fvgs_by_c3[bar_idx]
                if bar_idx >= self._sweep_bar_idx:
                    if self._dir == "bullish" and fvg.kind == "bullish":
                        self._pending_fvg = fvg
                    elif self._dir == "bearish" and fvg.kind == "bearish":
                        self._pending_fvg = fvg

        return None

    def on_close(self, trade, state: EngineState) -> None:
        pass

    def on_partial(self, trade, state: EngineState) -> None:
        pass
