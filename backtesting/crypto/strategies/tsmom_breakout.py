"""
Crypto donchian-breakout / time-series-momentum strategy.

Mechanism, fixed ex-ante from the literature (not fit to data):
  - Classic Donchian-channel breakout (Dennis/Eckhardt's "Turtle" system,
    1983): enter long on a close above the highest close of the last
    `entry_len` bars, short on a close below the lowest close of the same
    window. Different (shorter) `exit_len` channel closes the position on
    trend exhaustion -- asymmetric entry/exit avoids whipsawing on the
    same level.
  - Academically: this is the same mechanism as time-series momentum
    (Moskowitz, Ooi & Pedersen, "Time Series Momentum", JFE 2012) --
    positive risk-adjusted returns across 58 futures/forward/equity/bond/
    commodity markets over 25+ years, one of the most-replicated
    systematic strategies in existence. Crypto perpetuals are structurally
    the closest analog to the futures markets in that paper (funding-rate
    financed, no dividends/carry the way equities have), which is why this
    is the first mechanism tried for the crypto track rather than porting
    an equity-session concept (ORB/overnight-drift/closing-momentum) that
    doesn't map onto a 24/7 market with no cash session.
  - Sizing: fixed-fractional risk_pct per trade against an initial stop,
    same convention as every other strategy in this project -- NOT the
    volatility-targeting used in the academic TSMOM paper (that scales
    position size inversely to trailing realized vol to equalize risk
    contribution across assets in a multi-asset book; this is a single-
    asset per-instance backtest, so it's out of scope until/unless this
    strategy is run as a portfolio across multiple coins at once).

Stop modes (`stop_mode`), ready to A/B once real data lands -- this
project's standing lesson is that ATR-multiple stops sometimes work
(OvernightDrift, §29) and sometimes don't fix anything (IntradayMomentum,
§28), so a fallback is built in from the start rather than retrofitted:
  - "atr" (default): close -/+ stop_atr_mult * ATR(atr_period).
  - "structure": stop behind the nearest CONFIRMED swing low/high, via
    the same causal engine (`ict_structure.build_ict_structure_index`)
    already validated for both equity-index strategies. Falls back to atr
    if no swing is confirmed yet or the swing sits the wrong side of price.
  - "channel": stop at the exit-channel's opposite bound (the same
    `exit_len`-bar Donchian level used for exits) -- a lighter, Turtle-
    native alternative that needs no extra engine dependency: if price
    round-trips back through the SHORTER channel, the trend thesis is
    already broken, so use that level as the initial stop directly instead
    of an arbitrary ATR multiple.

No lookahead: entry/exit channel bounds and ATR are computed from bars
strictly BEFORE the current bar (channel excludes the current close).

Regime gate (`min_er`, disabled by default): filters entries to only fire
when Kaufman's Efficiency Ratio (`backtesting.engine.regime.efficiency_ratio`)
is above a threshold, i.e. only trade the breakout when price has actually
been trending, not chopping. UNLIKE every other design choice in this
file, this is NOT literature-backed for crypto or any other market --
web research (2026-07-05) found zero peer-reviewed or credible backtested
validation of ER/ADX/Choppiness-style regime filters, in crypto or
elsewhere; existing usage is retail-blog tier only. This is purely an
internal discovery/holdout hypothesis, motivated by real holdout losses
on BNBUSDT/DOGEUSDT (consistent with trend-following eating chop), not an
imported result. Treat any positive finding here with the same
overfitting suspicion as every other filter tested in this project.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.engine.regime import efficiency_ratio
from backtesting.features.ict_structure import build_ict_structure_index


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = np.full(len(close), np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


class CryptoTsmomBreakout(Strategy):
    def __init__(
        self,
        risk_pct: float = 0.005,
        direction: str = "both",
        entry_len: int = 20,     # Donchian entry channel (Turtle "System 1" length)
        exit_len: int = 10,      # shorter exit channel -- asymmetric to avoid whipsaw
        atr_period: int = 14,
        stop_atr_mult: float = 2.0,
        stop_mode: str = "atr",           # "atr", "structure", or "channel"
        structure_buffer_atr: float = 0.1,
        structure_left: int = 3,
        structure_right: int = 3,
        min_er: float | None = None,     # Kaufman ER regime gate -- None disables (default)
        er_period: int = 10,             # Kaufman's own published convention, not fit to data
    ):
        self.risk_pct = risk_pct
        self.direction = direction
        self.entry_len = entry_len
        self.exit_len = exit_len
        self.atr_period = atr_period
        self.stop_atr_mult = stop_atr_mult
        self.stop_mode = stop_mode
        self.structure_buffer_atr = structure_buffer_atr
        self.structure_left = structure_left
        self.structure_right = structure_right
        self.min_er = min_er
        self.er_period = er_period
        self._pos_dir = 0  # 0 flat, 1 long, -1 short -- tracked for should_close's exit-channel check

    def init(self, data: dict) -> None:
        df = next(iter(data.values())).copy()
        if "ts" in df.columns:
            df = df.set_index("ts", drop=False)
        df.sort_index(inplace=True)
        self._n = len(df)

        high = df["high"].to_numpy()
        low = df["low"].to_numpy()
        close = df["close"].to_numpy()
        self._close = close
        self._atr = _atr(high, low, close, self.atr_period)
        self._er = efficiency_ratio(close, self.er_period) if self.min_er is not None else None

        # Causal rolling channel: value at bar i uses only bars [i-len, i-1],
        # i.e. shift(1) before rolling so the current bar's own high/low/close
        # never leaks into its own entry/exit decision.
        high_s = pd.Series(high)
        low_s = pd.Series(low)
        self._entry_hi = high_s.shift(1).rolling(self.entry_len).max().to_numpy()
        self._entry_lo = low_s.shift(1).rolling(self.entry_len).min().to_numpy()
        self._exit_hi = high_s.shift(1).rolling(self.exit_len).max().to_numpy()
        self._exit_lo = low_s.shift(1).rolling(self.exit_len).min().to_numpy()

        self._last_hl = None
        self._last_ll = None
        self._last_lh = None
        self._last_hh = None
        if self.stop_mode == "structure":
            from backtesting.features.ict_structure import IctStructureConfig
            struct_df = df[["ts", "open", "high", "low", "close"]].reset_index(drop=True)
            cfg = IctStructureConfig(left=self.structure_left, right=self.structure_right)
            struct = build_ict_structure_index(struct_df, cfg)
            self._last_hl = struct["last_hl"].ffill().to_numpy()
            self._last_ll = struct["last_ll"].ffill().to_numpy()
            self._last_lh = struct["last_lh"].ffill().to_numpy()
            self._last_hh = struct["last_hh"].ffill().to_numpy()

        self._pos_dir = 0

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        i = bar.index
        if state.has_open_position:
            return None
        entry_hi, entry_lo = self._entry_hi[i], self._entry_lo[i]
        atr = self._atr[i]
        if np.isnan(entry_hi) or np.isnan(entry_lo) or np.isnan(atr) or atr <= 0:
            return None
        if self._er is not None:
            er = self._er[i]
            if np.isnan(er) or er < self.min_er:
                return None

        close = bar.close
        if close > entry_hi and self.direction in ("long", "both"):
            self._pos_dir = 1
            sl = self._compute_sl(i, close, atr, long=True)
            return Signal(direction=Direction.LONG, entry=close, sl=sl,
                          tp1=close + 50 * (close - sl),  # effectively disabled; exit-channel/SL are the real exits
                          risk_pct=self.risk_pct, tp1_frac=0.0, tp2_frac=0.0,
                          trail=False, label="crypto_tsmom_long")
        if close < entry_lo and self.direction in ("short", "both"):
            self._pos_dir = -1
            sl = self._compute_sl(i, close, atr, long=False)
            return Signal(direction=Direction.SHORT, entry=close, sl=sl,
                          tp1=close - 50 * (sl - close),
                          risk_pct=self.risk_pct, tp1_frac=0.0, tp2_frac=0.0,
                          trail=False, label="crypto_tsmom_short")
        return None

    def _compute_sl(self, i: int, close: float, atr: float, long: bool) -> float:
        atr_sl = close - self.stop_atr_mult * atr if long else close + self.stop_atr_mult * atr

        if self.stop_mode == "channel":
            level = self._exit_lo[i] if long else self._exit_hi[i]
            if np.isnan(level) or (level >= close if long else level <= close):
                return atr_sl
            return level

        if self.stop_mode == "structure":
            buf = self.structure_buffer_atr * atr
            if long:
                level = self._last_hl[i]
                if np.isnan(level):
                    level = self._last_ll[i]
                if np.isnan(level) or level >= close:
                    return atr_sl
                return level - buf
            else:
                level = self._last_lh[i]
                if np.isnan(level):
                    level = self._last_hh[i]
                if np.isnan(level) or level <= close:
                    return atr_sl
                return level + buf

        return atr_sl

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        i = bar.index
        exit_hi, exit_lo = self._exit_hi[i], self._exit_lo[i]
        if np.isnan(exit_hi) or np.isnan(exit_lo):
            return False
        label = getattr(position, "label", "") or ""
        if "long" in label:
            return bool(bar.close < exit_lo)
        if "short" in label:
            return bool(bar.close > exit_hi)
        return False

    def on_close(self, trade, state: EngineState) -> None:
        self._pos_dir = 0
