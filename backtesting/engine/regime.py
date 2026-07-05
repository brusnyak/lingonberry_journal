"""
Market regime classification — trend vs ranging vs volatility per pair.

Two layers:
  - efficiency_ratio(): standalone Kaufman ER function (kept, unchanged).
  - MarketRegime class: per-bar classification into 5 regimes using
    ER + ATR percentile.

Regime labels (exclusive, priority-ordered):
  volatile       — ATR % in top percentile (wide swings, high risk)
  low_vol        — ATR % in bottom percentile (compression, watch for breakout)
  trend_up       — strong directional move up (high ER, positive net change)
  trend_down     — strong directional move down (high ER, negative net change)
  ranging        — low directional persistence, normal volatility
  insufficient_data — not enough bars to classify yet

Usage:
    from backtesting.engine.regime import MarketRegime, RegimeConfig

    config = RegimeConfig()
    classifier = MarketRegime(config)
    labels, details = classifier.compute(df)
    labels[-1]  # latest bar's regime
    details["er"][-1]  # latest bar's ER
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine._utils import rolling_percentile


def efficiency_ratio(close: np.ndarray, period: int = 10) -> np.ndarray:
    """Kaufman's Efficiency Ratio — trend persistence vs. chop, causal.

    ER = |close[i] - close[i-n]| / sum(|close[j] - close[j-1]| for j in i-n+1..i)

    1.0 = pure trend (straight line), near 0 = pure chop.
    """
    n = len(close)
    er = np.full(n, np.nan)
    abs_diffs = np.abs(np.diff(close))
    for i in range(period, n):
        net_change = abs(close[i] - close[i - period])
        path_length = abs_diffs[i - period:i].sum()
        er[i] = net_change / path_length if path_length > 0 else 0.0
    return er


@dataclass
class RegimeConfig:
    """Configurable thresholds for regime classification.

    Defaults are tuned for 1h data (primary crypto entry TF). Adjust for
    lower/higher TFs or specific pair characteristics.
    """

    # Efficiency Ratio thresholds
    er_trend_threshold: float = 0.3       # ER above this = trending
    er_ranging_threshold: float = 0.15    # ER below this = ranging

    # Volatility thresholds (ATR % percentiles)
    volatile_atr_percentile: float = 0.85   # ATR % above this = volatile
    low_vol_atr_percentile: float = 0.15    # ATR % below this = low_vol

    # Computation periods
    er_period: int = 10
    atr_period: int = 14
    atr_percentile_window: int = 60  # rolling lookback for ATR % rank


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
         period: int) -> np.ndarray:
    """Average True Range, causal. Same computation as CryptoTsmomBreakout."""
    tr = np.maximum(
        high - low,
        np.maximum(
            np.abs(high - np.roll(close, 1)),
            np.abs(low - np.roll(close, 1)),
        ),
    )
    tr[0] = high[0] - low[0]
    atr = np.full(len(close), np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(close)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr



REGIME_LABELS = frozenset({
    "volatile", "low_vol", "trend_up", "trend_down",
    "ranging", "insufficient_data",
})


class MarketRegime:
    """Per-bar market regime classifier for a single pair.

    Pure computation: takes OHLCV, returns regime labels and raw metrics.
    No state — safe to call multiple times or share across strategies.
    """

    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()

    def compute(
        self,
        df: pd.DataFrame,
    ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        """Compute regime labels and detail metrics for every bar in ``df``.

        Parameters
        ----------
        df : pd.DataFrame
            Must have columns: high, low, close.

        Returns
        -------
        labels : np.ndarray[str]
            One label per bar (``REGIME_LABELS``).
        details : dict[str, np.ndarray]
            Raw metrics for debugging/visualisation:
            - "er" — efficiency ratio
            - "atr_pct" — ATR as % of close
            - "atr_percentile" — rolling percentile rank of ATR %
        """
        high = df["high"].to_numpy()
        low = df["low"].to_numpy()
        close = df["close"].to_numpy()
        n = len(close)

        # Guard: need enough bars to compute at least one valid indicator
        min_required = max(
            self.config.atr_period,
            self.config.er_period,
            self.config.atr_percentile_window,
        ) + 1
        if n < min_required:
            labels = np.full(n, "insufficient_data", dtype=object)
            empty = {k: np.full(n, np.nan) for k in ("er", "atr_pct", "atr_percentile")}
            return labels, empty

        er = efficiency_ratio(close, self.config.er_period)
        atr = _atr(high, low, close, self.config.atr_period)
        atr_pct = atr / np.maximum(close, 1e-9)
        atr_percentile = rolling_percentile(
            atr_pct, self.config.atr_percentile_window,
        )

        labels = np.full(n, "insufficient_data", dtype=object)
        for i in range(n):
            label = self._classify_one(i, er, atr_percentile, close)
            labels[i] = label

        return labels, {"er": er, "atr_pct": atr_pct,
                        "atr_percentile": atr_percentile}

    def _classify_one(
        self,
        i: int,
        er: np.ndarray,
        atr_percentile: np.ndarray,
        close: np.ndarray,
    ) -> str:
        """Classify a single bar. Priority order (first match wins)."""
        er_i = er[i]
        atr_pct_i = atr_percentile[i]

        if np.isnan(er_i) or np.isnan(atr_pct_i):
            return "insufficient_data"

        # 1. Abnormal volatility — overrides trend and ranging
        if atr_pct_i >= self.config.volatile_atr_percentile:
            return "volatile"

        # 2. Compression — potential breakout setup
        if atr_pct_i <= self.config.low_vol_atr_percentile:
            return "low_vol"

        # 3. Trend detection (requires ER period to be computable)
        if er_i >= self.config.er_trend_threshold:
            if i >= self.config.er_period:
                net_dir = close[i] - close[i - self.config.er_period]
                return "trend_up" if net_dir > 0 else "trend_down"
            return "ranging"  # early bar, can't determine direction

        # 4. Ranging
        if er_i <= self.config.er_ranging_threshold:
            return "ranging"

        # 5. Default: weak trend, normal vol — treat as ranging
        return "ranging"
