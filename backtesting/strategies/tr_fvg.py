"""
TR FVG — Fair Value Gap fill reversal.

Thesis:
  A 3-bar FVG (impulse + gap) creates an imbalance that price routinely returns to fill.
  The fill direction has a real t-statistic edge (research: fvg_bear_fill t=6.81 EURGBP 5m,
  avg_t=3.43 across 7/7 pairs on 5m). Enter on the bar the gap forms, targeting the fill.

Bearish FVG (LONG setup — "bear fill"):
  bar[i].high < bar[i-2].low → price gapped DOWN → fill is UP
  Entry: bar.close
  SL: OB-based (30m demand OB low - buffer) or bar extreme ± fixed buffer
  TP1: bar.close + tp1_r × risk

Bullish FVG (SHORT setup — "bull fill"):
  bar[i].low > bar[i-2].high → price gapped UP → fill is DOWN
  Entry: bar.close
  SL: OB-based (30m supply OB high + buffer) or bar extreme ± fixed buffer
  TP1: bar.close - tp1_r × risk

Direction modes:
  "bear"   — longs only (FVG fill up)
  "bull"   — shorts only (FVG fill down)
  "both"   — both
  "regime" — dynamic: 4H rolling trend score picks the dominant direction each bar.
             Switches to bull when recent 4H has more LL/LH than HH/HL.

SL modes:
  "fixed"     — bar extreme ± sl_buffer_pips (original)
  "structure" — nearest swing low/high within structure_sl_lookback bars, then ± buffer
                If no swing found in lookback, falls back to fixed.
  "ob_30m"   — demand/supply OB detected on 30m using proper ICT impulse-first algorithm.
                Requires "30" key in data dict. If no valid OB found (or stop < min floor),
                falls back to "fixed". SL = OB.low - sl_buffer_pips (long) or OB.high + sl_buffer_pips (short).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.engine.structure import StructureAnalyzer
from backtesting.structure_lib.swing import swing_points
from backtesting.structure_lib.labels import label_structure


class TrFvg(Strategy):
    """FVG fill reversal strategy."""

    spaces = {
        "sl_buffer_pips": [3, 5, 8, 10],
        "tp1_r": [0.8, 1.0, 1.5, 2.0],
        "min_gap_atr_pct": [0.2, 0.3, 0.5],
        "direction": ["bear", "bull", "both", "regime"],
    }

    def __init__(
        self,
        sl_buffer_pips: int = 5,
        tp1_r: float = 1.5,
        tp1_frac: float = 0.6,
        risk_pct: float = 0.005,
        pip_size: float = 0.0001,
        direction: str = "bear",
        min_gap_atr_pct: float = 0.3,
        # HTF filter
        htf_momentum_bars: int = 10,
        htf_agree: bool = True,
        # HTF structure — labeled 4H HH/HL/LH/LL trend filter
        # Uses structure_lib.label_structure for proper SMC multi-timeframe
        htf_structure: bool = False,       # enable 4H structure filter
        htf_swing_length: int = 7,         # swing detection width for 4H
        # Legacy — kept for backward compat, unused with label-based impl
        htf_struct_bars: int = 3,
        # Killzone filter (UTC hours)
        killzone: bool = False,
        kz_sessions: tuple = ((7, 10), (12, 16)),
        # SL mode
        sl_mode: str = "fixed",           # "fixed" | "structure" | "ob_30m"
        structure_sl_lookback: int = 20,  # bars to look back for structural swing
        structure_sl_swing_n: int = 3,    # fractal half-width for structural swing
        ob_sl_min_stop: float = 3.0,      # min stop distance in price units for ob_30m mode
        ob_sl_strict: bool = False,        # if True, skip trade when no valid OB (no fallback to fixed)
        # Regime-direction params (only used when direction="regime")
        regime_bars: int = 20,            # rolling 4H bars for regime scoring
    ):
        super().__init__()
        self.sl_buffer_pips = sl_buffer_pips
        self.tp1_r = tp1_r
        self.tp1_frac = tp1_frac
        self.risk_pct = risk_pct
        self.pip_size = pip_size
        self.direction = direction
        self.min_gap_atr_pct = min_gap_atr_pct
        self.htf_momentum_bars = htf_momentum_bars
        self.htf_agree = htf_agree
        self.htf_structure = htf_structure
        self.htf_swing_length = htf_swing_length
        self.htf_struct_bars = htf_struct_bars
        self.killzone = killzone
        self.kz_sessions = kz_sessions
        self.sl_mode = sl_mode
        self.structure_sl_lookback = structure_sl_lookback
        self.structure_sl_swing_n = structure_sl_swing_n
        self.ob_sl_min_stop = ob_sl_min_stop
        self.ob_sl_strict = ob_sl_strict
        self.regime_bars = regime_bars

    def _in_killzone(self, ts) -> bool:
        try:
            h = ts.hour
        except Exception:
            h = pd.Timestamp(ts).hour
        return any(s <= h < e for s, e in self.kz_sessions)

    def init(self, data: dict) -> None:
        entry_key = next(iter(data))
        df = data[entry_key].copy()
        if "ts" in df.columns:
            df = df.set_index("ts")
        df.sort_index(inplace=True)
        self._df = df

        h = df["high"].to_numpy()
        l = df["low"].to_numpy()
        c = np.roll(df["close"].to_numpy(), 1)
        c[0] = h[0]
        tr = np.maximum(h - l, np.maximum(np.abs(h - c), np.abs(l - c)))
        atr = pd.Series(tr).rolling(14).mean().to_numpy()
        self._atr = atr

        self._high  = h
        self._low   = l
        self._close = df["close"].to_numpy()
        self._n     = len(h)

        # Structural swing arrays for SL placement (structure mode)
        n = self.structure_sl_swing_n
        sh = np.full(self._n, np.nan)
        sl_arr = np.full(self._n, np.nan)
        for j in range(n, self._n - n):
            if h[j] == max(h[j - n: j + n + 1]):
                sh[j] = h[j]
            if l[j] == min(l[j - n: j + n + 1]):
                sl_arr[j] = l[j]
        self._swing_high = sh
        self._swing_low  = sl_arr

        # 30m OB structure analyzer — auto-resample from 5m if 30m not explicitly loaded
        self._sa_30m:    Optional[StructureAnalyzer] = None
        self._ts_30m:    Optional[np.ndarray] = None
        if self.sl_mode == "ob_30m":
            df30 = None
            if "30" in data and not data["30"].empty:
                df30 = data["30"].copy()
                if "ts" in df30.columns:
                    df30 = df30.set_index("ts")
                df30 = df30.sort_index()
            elif entry_key in data:
                # resample 5m → 30m on the fly
                df_src = data[entry_key].copy()
                if "ts" in df_src.columns:
                    df_src = df_src.set_index("ts")
                df_src = df_src.sort_index()
                df30_rs = df_src.resample("30min").agg(
                    {"open": "first", "high": "max", "low": "min",
                     "close": "last", "volume": "sum"}
                ).dropna(subset=["open"])
                df30 = df30_rs if not df30_rs.empty else None
            if df30 is not None:
                self._ts_30m = df30.index.to_numpy()
                self._sa_30m = StructureAnalyzer(
                    high=df30["high"].to_numpy(),
                    low=df30["low"].to_numpy(),
                    close=df30["close"].to_numpy(),
                    open_=df30["open"].to_numpy(),
                    swing_n=3,
                    ob_lookback=60,
                    ob_min_body_ratio=0.3,
                )

        # HTF filter / regime
        self._htf_ts:    Optional[np.ndarray] = None
        self._htf_dir:   Optional[np.ndarray] = None
        self._htf_high:  Optional[np.ndarray] = None
        self._htf_low:   Optional[np.ndarray] = None
        self._htf_trend: Optional[np.ndarray] = None   # 'bullish'/'bearish'/'neutral'/'transitional' per 4H bar
        self._htf_regime: Optional[np.ndarray] = None  # +1 bull, -1 bear, 0 neutral

        if "240" in data and (self.htf_agree or self.htf_structure or self.direction == "regime"):
            df4h = data["240"].copy()
            if "ts" in df4h.columns:
                df4h = df4h.set_index("ts")
            df4h = df4h.sort_index()
            delta = df4h["close"] - df4h["close"].shift(self.htf_momentum_bars)
            self._htf_ts   = df4h.index.to_numpy()
            self._htf_dir  = np.sign(delta).fillna(0).to_numpy()
            self._htf_high = df4h["high"].to_numpy()
            self._htf_low  = df4h["low"].to_numpy()

            # Proper SMC structure labels on 4H for htf_structure filter
            if self.htf_structure:
                try:
                    swings_4h, levels_4h = swing_points(df4h, swing_length=self.htf_swing_length)
                    struct_4h = label_structure(df4h, swings_4h, levels_4h)
                    self._htf_trend = struct_4h["trend"].to_numpy()
                except Exception:
                    self._htf_trend = None

            if self.direction == "regime":
                # Rolling sum of momentum signs over regime_bars — positive = bull regime, negative = bear
                rolling_score = (pd.Series(self._htf_dir)
                                 .rolling(self.regime_bars, min_periods=3)
                                 .sum()
                                 .fillna(0)
                                 .to_numpy())
                self._htf_regime = np.sign(rolling_score).astype(int)

    # ── Structural SL helpers ─────────────────────────────────────────────────

    def _structural_sl_long(self, before_i: int) -> Optional[float]:
        """Nearest confirmed swing low within lookback, excluding last swing_n bars."""
        confirmed = before_i - self.structure_sl_swing_n
        lo = max(0, confirmed - self.structure_sl_lookback)
        arr = self._swing_low[lo:confirmed]
        valid = arr[~np.isnan(arr)]
        return float(valid[-1]) if len(valid) > 0 else None

    def _structural_sl_short(self, before_i: int) -> Optional[float]:
        """Nearest confirmed swing high within lookback."""
        confirmed = before_i - self.structure_sl_swing_n
        lo = max(0, confirmed - self.structure_sl_lookback)
        arr = self._swing_high[lo:confirmed]
        valid = arr[~np.isnan(arr)]
        return float(valid[-1]) if len(valid) > 0 else None

    # ── HTF structure helpers ─────────────────────────────────────────────────
    # Uses proper label_structure engine on 4H data (installed in init()).
    # Trend values from labeling: 'bullish', 'bearish', 'neutral', 'transitional'.
    #
    #   long (bear fill) allowed in: bullish, neutral, transitional
    #   short (bull fill) allowed in: bearish, neutral, transitional

    def _htf_is_bullish_structure(self, idx4h: int) -> bool:
        """4H structure supports longs."""
        if self._htf_trend is None or idx4h < 0 or idx4h >= len(self._htf_trend):
            return True  # no data = no filter
        trend = self._htf_trend[idx4h]
        return trend in ("bullish", "neutral", "transitional")

    def _htf_is_bearish_structure(self, idx4h: int) -> bool:
        """4H structure supports shorts."""
        if self._htf_trend is None or idx4h < 0 or idx4h >= len(self._htf_trend):
            return True
        trend = self._htf_trend[idx4h]
        return trend in ("bearish", "neutral", "transitional")

    # ── Main logic ────────────────────────────────────────────────────────────

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index

        # ── Structure-based trailing on open position ──────────────────────
        if state.has_open_position:
            pos = state.open_positions[0]
            if hasattr(self, "_swing_high") and hasattr(self, "_swing_low"):
                confirmed = max(0, i - self.structure_sl_swing_n - 1)
                if pos.direction == 1 or (hasattr(pos.direction, 'value') and pos.direction.value == 1) or str(pos.direction) == 'Direction.LONG':
                    # Long: trail on most recent swing low above current SL
                    lo = max(0, confirmed - self.structure_sl_lookback)
                    lows = self._swing_low[lo:confirmed]
                    valid = lows[~np.isnan(lows)]
                    if len(valid) > 0:
                        new_sl = float(valid[-1]) - self.sl_buffer_pips * self.pip_size
                        if new_sl > pos.sl and bar.close > new_sl:
                            self.update_sl(pos.id, new_sl)
                else:
                    # Short: trail on most recent swing high below current SL
                    lo = max(0, confirmed - self.structure_sl_lookback)
                    highs = self._swing_high[lo:confirmed]
                    valid = highs[~np.isnan(highs)]
                    if len(valid) > 0:
                        new_sl = float(valid[-1]) + self.sl_buffer_pips * self.pip_size
                        if new_sl < pos.sl and bar.close < new_sl:
                            self.update_sl(pos.id, new_sl)
            return None

        if i < max(3, self.structure_sl_swing_n * 2 + 2):
            return None

        if self.killzone and not self._in_killzone(bar.ts):
            return None

        atr = self._atr[i]
        if np.isnan(atr) or atr <= 0:
            return None

        gap_thresh = atr * self.min_gap_atr_pct
        pip    = self.pip_size
        sl_buf = self.sl_buffer_pips * pip

        b0_high  = self._high[i]
        b0_low   = self._low[i]
        b0_close = self._close[i]
        b2_high  = self._high[i - 2]
        b2_low   = self._low[i - 2]

        # HTF direction
        htf = 0
        idx4h = -1
        regime = 0
        if self._htf_ts is not None:
            idx4h = int(np.searchsorted(self._htf_ts, bar.ts, side="right")) - 1
            if idx4h >= 0:
                htf = int(self._htf_dir[idx4h])
                if self._htf_regime is not None:
                    regime = int(self._htf_regime[idx4h])

        # Resolve effective direction
        eff_dir = self.direction
        if eff_dir == "regime":
            # regime > 0 = 4H trending up → take bear fills (longs, price dips to fill)
            # regime < 0 = 4H trending down → take bull fills (shorts, price rallies to fill)
            if regime > 0:
                eff_dir = "bear"
            elif regime < 0:
                eff_dir = "bull"
            else:
                return None  # neutral regime — skip

        # ── Bearish FVG → LONG ────────────────────────────────────────────────
        if eff_dir in ("bear", "both"):
            if b0_high < b2_low:
                gap = b2_low - b0_high
                if gap >= gap_thresh:
                    if self.htf_agree and htf < 0:
                        pass
                    elif self.htf_structure and idx4h >= 0 and not self._htf_is_bullish_structure(idx4h):
                        pass
                    else:
                        sl = None
                        if self.sl_mode == "structure":
                            sw = self._structural_sl_long(i)
                            sl = (sw - sl_buf) if sw is not None else (b0_low - sl_buf)
                            sl = max(sl, b0_low - sl_buf * 3)
                        elif self.sl_mode == "ob_30m" and self._sa_30m is not None:
                            idx30 = int(np.searchsorted(self._ts_30m, bar.ts, side="right")) - 1
                            if idx30 >= 3:
                                ob = self._sa_30m.demand_ob_before(idx30)
                                if ob is not None:
                                    ob_sl = ob.low - sl_buf
                                    stop_dist = b0_close - ob_sl
                                    if stop_dist >= self.ob_sl_min_stop:
                                        sl = ob_sl
                        if sl is None:
                            if self.ob_sl_strict and self.sl_mode == "ob_30m":
                                return None  # no valid OB → skip trade
                            sl = b0_low - (200 * self.pip_size)  # fallback to fixed 200-pip

                        stop = b0_close - sl
                        if stop > 0:
                            return Signal(
                                direction=Direction.LONG,
                                entry=b0_close,
                                sl=sl,
                                tp1=b0_close + self.tp1_r * stop,
                                risk_pct=self.risk_pct,
                                tp1_frac=self.tp1_frac,
                                tp2_frac=0.0,
                                trail=True,
                                label="fvg_bear_fill",
                            )

        # ── Bullish FVG → SHORT ───────────────────────────────────────────────
        if eff_dir in ("bull", "both"):
            if b0_low > b2_high:
                gap = b0_low - b2_high
                if gap >= gap_thresh:
                    if self.htf_agree and htf > 0:
                        pass
                    elif self.htf_structure and idx4h >= 0 and not self._htf_is_bearish_structure(idx4h):
                        pass
                    else:
                        sl = None
                        if self.sl_mode == "structure":
                            sw = self._structural_sl_short(i)
                            sl = (sw + sl_buf) if sw is not None else (b0_high + sl_buf)
                            sl = min(sl, b0_high + sl_buf * 3)
                        elif self.sl_mode == "ob_30m" and self._sa_30m is not None:
                            idx30 = int(np.searchsorted(self._ts_30m, bar.ts, side="right")) - 1
                            if idx30 >= 3:
                                ob = self._sa_30m.supply_ob_before(idx30)
                                if ob is not None:
                                    ob_sl = ob.high + sl_buf
                                    stop_dist = ob_sl - b0_close
                                    if stop_dist >= self.ob_sl_min_stop:
                                        sl = ob_sl
                        if sl is None:
                            if self.ob_sl_strict and self.sl_mode == "ob_30m":
                                return None
                            sl = b0_high + (200 * self.pip_size)

                        stop = sl - b0_close
                        if stop > 0:
                            return Signal(
                                direction=Direction.SHORT,
                                entry=b0_close,
                                sl=sl,
                                tp1=b0_close - self.tp1_r * stop,
                                risk_pct=self.risk_pct,
                                tp1_frac=self.tp1_frac,
                                tp2_frac=0.0,
                                trail=True,
                                label="fvg_bull_fill",
                            )

        return None
