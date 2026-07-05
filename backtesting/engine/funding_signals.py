"""
Funding rate signal engine — crypto-native signal from perpetual swap funding.

Funding rate extremes predict short-term reversals in crypto markets:
  - Very positive funding → longs paying shorts → market overleveraged long → short signal
  - Very negative funding → shorts paying longs → market overleveraged short → long signal

This is a genuinely crypto-native edge. No forex analog exists.

Output: signal strength from -1.0 (strong short) to +1.0 (strong long), aligned to
the input funding rate DataFrame. Strategies index into the signal array to check
current funding sentiment before entering trades.

Usage:
    from backtesting.engine.funding_signals import FundingSignalEngine, FundingSignalConfig

    config = FundingSignalConfig()
    engine = FundingSignalEngine(config)
    result = engine.compute(funding_df)
    result.signals[-1]   # -1.0 to 1.0
    result.percentiles[-1]  # 0.0 to 1.0
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class FundingSignalConfig:
    """Configurable thresholds for funding-rate-based signals.

    Defaults tuned for 8h funding data (Binance/Bybit convention).
    Adjust ``lookback_bars`` for different sampling frequencies.
    """

    # Rolling percentile window (in data rows, not hours)
    lookback_bars: int = 42            # 14 days at 8h (= 3 bars/day)

    # Percentile thresholds for signal mapping
    long_signal_pct: float = 0.10      # bottom 10% → strong long signal
    short_signal_pct: float = 0.90     # top 10% → strong short signal
    neutral_lower_pct: float = 0.30    # below 30th → weak long bias
    neutral_upper_pct: float = 0.70    # above 70th → weak short bias

    # Minimum absolute funding rate to register any signal (filters noise)
    min_abs_funding: float = 1e-6

    # If both are 0.0, no cooldown. Otherwise, oldest allowed bar index
    # for the "last extreme signal". This is handled by the strategy, not
    # the engine — the engine always returns the raw signal strength.


@dataclass
class FundingSignalResult:
    """Output from ``FundingSignalEngine.compute()``.

    All arrays are aligned to the input ``funding_df`` rows (one entry per row).
    """
    signals: np.ndarray       # float: -1.0 to 1.0
    percentiles: np.ndarray   # float: 0.0 to 1.0
    z_scores: np.ndarray      # float: standard deviations from mean
    raw: np.ndarray           # float: the raw funding rate values


_FUNDING_SIGNAL_LABELS = frozenset({
    "strong_long", "weak_long", "neutral", "weak_short", "strong_short",
    "insufficient_data",
})


def label_from_signal(signal: float) -> str:
    """Convert a signal strength to a human-readable label."""
    if np.isnan(signal):
        return "insufficient_data"
    if signal >= 0.8:
        return "strong_long"
    if signal >= 0.3:
        return "weak_long"
    if signal > -0.3:
        return "neutral"
    if signal > -0.8:
        return "weak_short"
    return "strong_short"


class FundingSignalEngine:
    """Compute funding-rate-based trading signals for a single pair.

    Pure computation: takes a funding rate DataFrame, returns signal arrays.
    No state — safe to call multiple times or share across strategies.
    """

    def __init__(self, config: Optional[FundingSignalConfig] = None):
        self.config = config or FundingSignalConfig()

    def compute(self, funding_df: pd.DataFrame) -> FundingSignalResult:
        """Compute funding signals for every row in ``funding_df``.

        Parameters
        ----------
        funding_df : pd.DataFrame
            Must have a ``fundingRate`` column. Typically from
            ``backtesting.crypto.data.load_funding_rate()``.

        Returns
        -------
        FundingSignalResult with arrays aligned to ``funding_df`` rows.
        """
        rates = funding_df["fundingRate"].to_numpy()
        n = len(rates)

        percentiles = self._rolling_percentile(rates, self.config.lookback_bars)
        z_scores = self._rolling_zscore(rates, self.config.lookback_bars)
        signals = self._compute_signals(rates, percentiles)

        return FundingSignalResult(
            signals=signals,
            percentiles=percentiles,
            z_scores=z_scores,
            raw=rates.copy(),
        )

    def _rolling_percentile(
        self, values: np.ndarray, window: int
    ) -> np.ndarray:
        """Causal rolling percentile rank of current vs prior ``window`` values.

        Returns 0..1 float. First ``window`` bars are NaN (insufficient data).
        Early division by valid (non-NaN) count avoids depressed percentiles.
        """
        n = len(values)
        result = np.full(n, np.nan)
        for i in range(window, n):
            prior = values[i - window:i]
            valid = prior[~np.isnan(prior)]
            if len(valid) < 5:
                continue
            rank = float(np.sum(valid < values[i])) / len(valid)
            result[i] = rank
        return result

    def _rolling_zscore(
        self, values: np.ndarray, window: int
    ) -> np.ndarray:
        """Causal rolling z-score of current vs prior ``window`` values."""
        n = len(values)
        result = np.full(n, np.nan)
        for i in range(window, n):
            prior = values[i - window:i]
            valid = prior[~np.isnan(prior)]
            if len(valid) < 5:
                continue
            mu = float(np.mean(valid))
            sd = float(np.std(valid, ddof=1))
            if sd > 0:
                result[i] = (values[i] - mu) / sd
            else:
                result[i] = 0.0
        return result

    def _compute_signals(
        self,
        rates: np.ndarray,
        percentiles: np.ndarray,
    ) -> np.ndarray:
        """Map percentile rank to signal strength in [-1, 1].

        Signal convention:
          +1.0 = strong LONG  (funding is very negative — shorts paying)
          -1.0 = strong SHORT (funding is very positive — longs paying)
           0.0 = neutral

        Mapping (configurable thresholds):
          pct <= long_signal_pct          →  1.0  (strong long)
          long_signal_pct < pct <= neutral_lower_pct  →  0.5  (weak long)
          neutral_lower_pct < pct < neutral_upper_pct →  0.0  (neutral)
          neutral_upper_pct <= pct < short_signal_pct  → -0.5  (weak short)
          pct >= short_signal_pct        → -1.0  (strong short)
        """
        cfg = self.config
        n = len(rates)
        signals = np.full(n, np.nan)

        for i in range(n):
            pct = percentiles[i]
            if np.isnan(pct):
                continue

            # Skip if absolute funding rate is too small (noise filter)
            if abs(rates[i]) < cfg.min_abs_funding:
                signals[i] = 0.0
                continue

            if pct <= cfg.long_signal_pct:
                signals[i] = 1.0
            elif pct <= cfg.neutral_lower_pct:
                signals[i] = 0.5
            elif pct < cfg.neutral_upper_pct:
                signals[i] = 0.0
            elif pct < cfg.short_signal_pct:
                signals[i] = -0.5
            else:
                signals[i] = -1.0

        return signals
