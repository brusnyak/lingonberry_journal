"""Kaufman's Efficiency Ratio — trend persistence vs. chop, causal, reusable.

ER = |close[i] - close[i-n]| / sum(|close[j] - close[j-1]| for j in i-n+1..i)

1.0 = pure trend (straight line), near 0 = pure chop (price churns, no net
progress). Standard params (period=10) per Kaufman's published convention —
not fit to this dataset.
"""
from __future__ import annotations

import numpy as np


def efficiency_ratio(close: np.ndarray, period: int = 10) -> np.ndarray:
    n = len(close)
    er = np.full(n, np.nan)
    abs_diffs = np.abs(np.diff(close))
    for i in range(period, n):
        net_change = abs(close[i] - close[i - period])
        path_length = abs_diffs[i - period:i].sum()
        er[i] = net_change / path_length if path_length > 0 else 0.0
    return er
