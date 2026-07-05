"""
Shared utility functions for the backtesting engine.

Rolling percentile / z-score computations used across multiple modules.
"""
from __future__ import annotations

import numpy as np


def rolling_percentile(values: np.ndarray, window: int) -> np.ndarray:
    """Causal rolling percentile rank of current vs prior ``window`` values.

    Returns 0..1 float. First ``window`` bars are NaN (insufficient data).
    Handles NaN values in the series: prior NaN values are stripped before
    ranking, and the denominator is the count of valid priors (not the window).

    The result uses tie-aware ranking: ``(n_less + 0.5 * n_equal) / total``.
    This prevents all-equal values from spuriously signaling extreme (0 or 1).
    """
    n = len(values)
    result = np.full(n, np.nan)
    for i in range(window, n):
        prior = values[i - window : i]
        valid = prior[~np.isnan(prior)]
        if len(valid) < 5:
            continue  # too few comparisons — leave as NaN
        n_less = int(np.sum(valid < values[i]))
        n_equal = int(np.sum(valid == values[i]))
        rank = (n_less + 0.5 * n_equal) / len(valid)
        result[i] = rank
    return result


def rolling_zscore(values: np.ndarray, window: int) -> np.ndarray:
    """Causal rolling z-score of current vs prior ``window`` values.

    Zeros out when lookback standard deviation is zero (all values identical).
    """
    n = len(values)
    result = np.full(n, np.nan)
    for i in range(window, n):
        prior = values[i - window : i]
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
