"""
Crypto funding-rate mean-reversion strategy.

Mechanism:
  - Funding rate extremes predict short-term reversals in crypto perps:
    • Very negative funding (shorts paying heavily) → overcrowded short → long signal
    • Very positive funding (longs paying heavily) → overcrowded long → short signal
  - This is a genuinely crypto-native signal. No forex analog exists.
  - Entry: firing when the funding signal engine outputs a strong signal (|signal| >= 0.8).
  - Exit: standard SL (atr / structure / channel). TP is the opposite-funding reversal
    back toward neutral (disengaged when signal |z-score| drops below 1.0).

No lookahead: funding signals are computed from rolling percentiles of strictly
prior bars (causal, via FundingSignalEngine).

Compare to CryptoTsmomBreakout: this is mean-reversion, not trend-following.
They are orthogonal strategies — one wins in trending regimes, one wins at extremes.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.funding_signals import (
    FundingSignalConfig,
    FundingSignalEngine,
)
from backtesting.engine.orders import Direction, Signal
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


class CryptoFundingMeanRev(Strategy):
    """Mean-reversion on funding rate extremes; uses same stop convention as TSMOM.

    Params
    ------
    risk_pct : float
        Fraction of equity risked per trade.
    direction : str
        "long", "short", or "both".
    atr_period : int
        Period for ATR computation (same as TSMOM).
    stop_atr_mult : float
        ATR multiple for initial stop distance.
    stop_mode : str
        "atr", "structure", or "channel".
    entry_threshold : float
        Minimum |signal| to trigger entry (default 0.8 = strong signal).
    """

    _signal_source = "init_precomputed"

    spaces = {
        "risk_pct": [0.005],
        "stop_atr_mult": [2.0, 3.0],
        "stop_mode": ["atr", "channel"],
        "entry_threshold": [0.8],
    }

    def __init__(
        self,
        risk_pct: float = 0.005,
        direction: str = "both",
        atr_period: int = 14,
        stop_atr_mult: float = 2.0,
        stop_mode: str = "atr",
        structure_buffer_atr: float = 0.1,
        structure_left: int = 3,
        structure_right: int = 3,
        entry_threshold: float = 0.8,
    ):
        self.risk_pct = risk_pct
        self.direction = direction
        self.atr_period = atr_period
        self.stop_atr_mult = stop_atr_mult
        self.stop_mode = stop_mode
        self.structure_buffer_atr = structure_buffer_atr
        self.structure_left = structure_left
        self.structure_right = structure_right
        self.entry_threshold = entry_threshold

        # Populated in init()
        self._funding_signals: Optional[np.ndarray] = None
        self._atr: Optional[np.ndarray] = None
        self._close: Optional[np.ndarray] = None

    def init(self, data: dict) -> None:
        df = next(iter(data.values())).copy()
        if "ts" in df.columns:
            df = df.set_index("ts", drop=False)
        df.sort_index(inplace=True)
        self._n = len(df)
        ohlcv_ts = pd.to_datetime(df["ts"], utc=True) if "ts" in df.columns else df.index

        high = df["high"].to_numpy()
        low = df["low"].to_numpy()
        close = df["close"].to_numpy()
        self._close = close
        self._atr = _atr(high, low, close, self.atr_period)

        # ── Precompute funding signals, aligned by timestamp ──
        self._funding_signals: Optional[np.ndarray] = None
        funding_df: Optional[pd.DataFrame] = data.get("funding")
        if funding_df is not None and not funding_df.empty:
            engine = FundingSignalEngine(FundingSignalConfig())
            result = engine.compute(funding_df)
            # Build a Series: funding timestamp → signal value
            fts = pd.to_datetime(funding_df["ts"], utc=True)
            sig_series = pd.Series(result.signals, index=fts).sort_index()
            # Align to OHLCV bars by forward-fill: each OHLCV bar gets the
            # most recent funding signal available at that time.
            self._funding_signals = sig_series.reindex(ohlcv_ts, method="ffill").to_numpy()

        # ── Precompute structure (if needed) ──
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

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None

        i = bar.index
        atr = self._atr[i] if self._atr is not None else np.nan
        if np.isnan(atr) or atr <= 0:
            return None

        # Get funding signal at current bar index
        signal = self._current_funding_signal(i)
        if signal is None:
            return None

        close = bar.close
        threshold = self.entry_threshold

        if signal >= threshold and self.direction in ("long", "both"):
            # Strong long signal (funding very negative — shorts paying)
            sl = self._compute_sl(i, close, atr, long=True)
            return Signal(
                direction=Direction.LONG, entry=close, sl=sl,
                tp1=close + 50 * (close - sl),
                risk_pct=self.risk_pct, tp1_frac=0.0, tp2_frac=0.0,
                trail=False, label="funding_meanrev_long",
            )

        if signal <= -threshold and self.direction in ("short", "both"):
            # Strong short signal (funding very positive — longs paying)
            sl = self._compute_sl(i, close, atr, long=False)
            return Signal(
                direction=Direction.SHORT, entry=close, sl=sl,
                tp1=close - 50 * (sl - close),
                risk_pct=self.risk_pct, tp1_frac=0.0, tp2_frac=0.0,
                trail=False, label="funding_meanrev_short",
            )

        return None

    def _current_funding_signal(self, bar_index: int) -> Optional[float]:
        """Get the funding signal strength at a given OHLCV bar index.

        Uses the timestamp-aligned funding signal array from ``init()``.
        Returns None if no funding data or the signal is NaN.
        """
        if self._funding_signals is None:
            return None
        if bar_index >= len(self._funding_signals):
            return None
        val = self._funding_signals[bar_index]
        if np.isnan(val):
            return None
        return float(val)

    def _compute_sl(self, i: int, close: float, atr: float, long: bool) -> float:
        atr_sl = close - self.stop_atr_mult * atr if long else close + self.stop_atr_mult * atr

        if self.stop_mode == "channel":
            # Channel stop: not applicable here (no Donchian channel)
            return atr_sl

        if self.stop_mode == "structure":
            buf = self.structure_buffer_atr * atr
            if long:
                level = self._last_hl[i] if self._last_hl is not None else np.nan
                if np.isnan(level):
                    level = self._last_ll[i] if self._last_ll is not None else np.nan
                if np.isnan(level) or level >= close:
                    return atr_sl
                return level - buf
            else:
                level = self._last_lh[i] if self._last_lh is not None else np.nan
                if np.isnan(level):
                    level = self._last_hh[i] if self._last_hh is not None else np.nan
                if np.isnan(level) or level <= close:
                    return atr_sl
                return level + buf

        return atr_sl

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        """Exit when funding signal returns to neutral (z-score < 1)."""
        i = bar.index
        sig = self._current_funding_signal(i)
        if sig is None:
            return False
        label = getattr(position, "label", "") or ""
        if "long" in label and sig < 0.3:
            return True
        if "short" in label and sig > -0.3:
            return True
        return False
