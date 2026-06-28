"""
TR VWAP — VWAP bounce with EMA9/21 trend bias.

Thesis:
  VWAP acts as dynamic support/resistance. When price pushes outside the ±1σ
  band and closes back inside, it signals the rejection. EMA9/21 crossover
  provides directional bias — only take bounces in the bias direction.

Entry rules (all must pass):
  1. EMA9 > EMA21 → bullish bias (long only). EMA9 < EMA21 → bearish (short only).
  2. Price was outside ±1σ band (prev close < VWAP_1L or > VWAP_1H).
  3. Current bar closes back inside the band.
  4. HTF filter (optional): 4H momentum agrees with trade direction.
  5. Killzone (optional): bar timestamp in London/NY sessions.

Exit:
  SL: max(VWAP_2σ band, ATR-based minimum stop)
  TP1: 1.5R fixed
  Trail: active after TP1 hit

Parameter spaces for sweeping:
  ema_fast:      [5, 9, 13]
  ema_slow:      [13, 21, 34]
  tp_r:          [0.8, 1.0, 1.5, 2.0]
  sl_atr_mult:   [1.0, 1.5, 2.0]
  min_bounce_gap_pct: [0.5, 1.0, 2.0]  (* pip_size, minimum distance outside band)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.features.vwap import build_vwap_index


class TrVwap(Strategy):
    """VWAP bounce with EMA9/21 trend bias."""

    spaces = {
        "ema_fast": [5, 9, 13],
        "ema_slow": [13, 21, 34],
        "tp_r": [0.8, 1.0, 1.5, 2.0],
        "sl_atr_mult": [1.0, 1.5, 2.0],
        "min_bounce_gap_pips": [0.5, 1.0, 2.0],
    }

    def __init__(
        self,
        # EMA trend
        ema_fast: int = 9,
        ema_slow: int = 21,
        # Risk
        tp_r: float = 1.5,
        sl_atr_mult: float = 1.5,
        risk_pct: float = 0.005,
        pip_size: float = 0.0001,
        # Bounce filter
        min_bounce_gap_pips: float = 0.5,
        # HTF filter
        htf_momentum_bars: int = 10,
        htf_agree: bool = True,
        # Killzone
        killzone: bool = False,
        kz_sessions: tuple = ((7, 10), (12, 16)),
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.tp_r = tp_r
        self.sl_atr_mult = sl_atr_mult
        self.risk_pct = risk_pct
        self.pip_size = pip_size
        self.min_bounce_gap_pips = min_bounce_gap_pips
        self.htf_momentum_bars = htf_momentum_bars
        self.htf_agree = htf_agree
        self.killzone = killzone
        self.kz_sessions = kz_sessions

    def _in_killzone(self, ts) -> bool:
        try:
            h = ts.hour
        except Exception:
            h = pd.Timestamp(ts).hour
        return any(s <= h < e for s, e in self.kz_sessions)

    def _ema(self, arr: np.ndarray, period: int) -> np.ndarray:
        """Causal EMA using recursive formula."""
        out = np.full(len(arr), np.nan, dtype=float)
        if len(arr) == 0:
            return out
        alpha = 2.0 / (period + 1)
        out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
        return out

    def init(self, data: dict) -> None:
        entry_key = next(iter(data))
        df = data[entry_key].copy()

        # Compute VWAP features
        df_vwap = build_vwap_index(df)

        # Compute EMAs on close
        close_arr = df_vwap["close"].to_numpy()
        self._ema_f = self._ema(close_arr, self.ema_fast)
        self._ema_s = self._ema(close_arr, self.ema_slow)
        self._close = close_arr
        self._high = df_vwap["high"].to_numpy()
        self._low = df_vwap["low"].to_numpy()
        self._n = len(close_arr)

        # Store VWAP columns
        for col in ["vwap", "vwap_1l", "vwap_1h", "vwap_2l", "vwap_2h",
                     "vwap_bounce_long", "vwap_bounce_short", "vwap_position",
                     "vwap_trend", "vwap_z_score"]:
            if col in df_vwap.columns:
                setattr(self, f"_{col}", df_vwap[col].to_numpy())

        # ATR
        tr = np.maximum(
            self._high - self._low,
            np.maximum(
                np.abs(self._high - np.roll(self._close, 1)),
                np.abs(self._low - np.roll(self._close, 1)),
            ),
        )
        tr[0] = self._high[0] - self._low[0]
        atr = pd.Series(tr).rolling(14).mean().to_numpy()
        self._atr = atr

        # HTF direction (4H)
        self._htf_ts: Optional[np.ndarray] = None
        self._htf_dir: Optional[np.ndarray] = None
        if "240" in data and self.htf_agree:
            df4h = data["240"].copy()
            if "ts" in df4h.columns:
                df4h = df4h.set_index("ts")
            df4h = df4h.sort_index()
            delta = df4h["close"] - df4h["close"].shift(self.htf_momentum_bars)
            self._htf_ts = df4h.index.to_numpy()
            self._htf_dir = np.sign(delta).fillna(0).to_numpy()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None

        i = bar.index
        warmup = max(self.ema_slow + 5, 20)
        if i < warmup:
            return None

        # Killzone
        if self.killzone and not self._in_killzone(bar.ts):
            return None

        # ATR must be valid
        atr = self._atr[i]
        if np.isnan(atr) or atr <= 0:
            return None

        # ── Bias: EMA9 vs EMA21 ───────────────────────────────────────────
        ema_f = self._ema_f[i]
        ema_s = self._ema_s[i]
        if np.isnan(ema_f) or np.isnan(ema_s):
            return None

        bullish_bias = ema_f > ema_s
        bearish_bias = ema_f < ema_s

        # If EMAs are crossing (very close), don't trade
        if abs(ema_f - ema_s) < 0.1 * self.pip_size:
            return None

        # ── HTF agreement (optional) ──────────────────────────────────────
        if self.htf_agree and self._htf_ts is not None and self._htf_dir is not None:
            idx4h = int(np.searchsorted(self._htf_ts, bar.ts, side="right")) - 1
            if idx4h >= 0:
                htf_dir = int(self._htf_dir[idx4h])
                if bullish_bias and htf_dir < 0:
                    return None  # 4H says down, skip long
                if bearish_bias and htf_dir > 0:
                    return None  # 4H says up, skip short

        # ── Bounce detection ──────────────────────────────────────────────
        pip = self.pip_size
        min_gap = self.min_bounce_gap_pips * pip

        vwap_1l = self._vwap_1l[i]
        vwap_1h = self._vwap_1h[i]
        vwap_2l = self._vwap_2l[i]
        vwap_2h = self._vwap_2h[i]
        close_i = self._close[i]
        prev_close = self._close[i - 1]

        # Need VWAP values to be valid
        if np.isnan(vwap_1l) or np.isnan(vwap_1h):
            return None

        # ── LONG: bullish bias + bounce from lower band ───────────────────
        if bullish_bias:
            bounce_long = bool(self._vwap_bounce_long[i])
            if bounce_long:
                # Verify gap was meaningful
                prev_1l = self._vwap_1l[i - 1]
                if not np.isnan(prev_1l) and (prev_1l - prev_close) >= min_gap:
                    # SL: at VWAP_2L or ATR-based, whichever is tighter
                    sl_dist_atr = self.sl_atr_mult * atr
                    sl_by_atr = close_i - sl_dist_atr
                    sl_by_band = vwap_2l if not np.isnan(vwap_2l) else sl_by_atr
                    sl = max(sl_by_atr, sl_by_band)  # tighter stop

                    stop_dist = close_i - sl
                    if stop_dist > pip:  # at least 1 pip stop
                        return Signal(
                            direction=Direction.LONG,
                            entry=close_i,
                            sl=sl,
                            tp1=close_i + self.tp_r * stop_dist,
                            risk_pct=self.risk_pct,
                            tp1_frac=0.6,
                            tp2_frac=0.0,
                            trail=True,
                            label="vwap_bounce_long",
                        )

        # ── SHORT: bearish bias + bounce from upper band ──────────────────
        if bearish_bias:
            bounce_short = bool(self._vwap_bounce_short[i])
            if bounce_short:
                prev_1h = self._vwap_1h[i - 1]
                if not np.isnan(prev_1h) and (prev_close - prev_1h) >= min_gap:
                    sl_dist_atr = self.sl_atr_mult * atr
                    sl_by_atr = close_i + sl_dist_atr
                    sl_by_band = vwap_2h if not np.isnan(vwap_2h) else sl_by_atr
                    sl = min(sl_by_atr, sl_by_band)

                    stop_dist = sl - close_i
                    if stop_dist > pip:
                        return Signal(
                            direction=Direction.SHORT,
                            entry=close_i,
                            sl=sl,
                            tp1=close_i - self.tp_r * stop_dist,
                            risk_pct=self.risk_pct,
                            tp1_frac=0.6,
                            tp2_frac=0.0,
                            trail=True,
                            label="vwap_bounce_short",
                        )

        return None
