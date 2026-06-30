"""
Time-series cross-validation with purging (remove overlapping data) and
embargo (gap between train and test to prevent leakage).

Standard sklearn KFold/TimeSeriesSplit is not sufficient for financial data
because adjacent bars are autocorrelated. Purging removes test-set observations
that overlap with the training window; embargo inserts a gap between train and test.
"""

from __future__ import annotations

from typing import Iterator

import numpy as np


def purge_embargo_split(
    n: int,
    n_splits: int = 5,
    embargo: int = 5,
    purge: bool = True,
    min_train: int = 100,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """
    Time-series CV split with purging and embargo.

    Each split:
      - Train: contiguous block at the start
      - Test: next contiguous block after an embargo gap

    Args:
        n: total number of samples
        n_splits: number of train/test pairs
        embargo: bars to skip between train and test (prevents leakage)
        purge: if True, remove test indices from train set (on by default)
        min_train: minimum train samples required per split

    Yields:
        (train_indices, test_indices) for each split
    """
    if n < min_train + embargo + 10:
        return

    test_size = max(1, (n - min_train) // n_splits)
    for i in range(n_splits):
        test_end = n - i * test_size
        test_start = max(min_train, test_end - test_size)

        if test_start < min_train:
            break

        train_end = test_start - embargo
        if train_end < min_train:
            break

        test_idx = np.arange(test_start, test_end)
        train_idx = np.arange(0, train_end)

        if purge:
            # Remove any train indices that overlap with test window
            train_idx = train_idx[~np.isin(train_idx, test_idx)]

        if len(train_idx) < min_train or len(test_idx) < 1:
            break

        yield train_idx, test_idx


def rolling_window_split(
    n: int,
    window_size: int = 2000,
    test_size: int = 500,
    step: int = 250,
    embargo: int = 5,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """
    Rolling window split for backtesting.

    Each split uses a fixed-size training window sliding forward.
    Test set immediately follows (after embargo gap).

    Args:
        n: total number of samples
        window_size: training window length
        test_size: test window length
        step: how far to slide the window each iteration
        embargo: gap bars between train and test

    Yields:
        (train_indices, test_indices)
    """
    start = 0
    while start + window_size + test_size + embargo <= n:
        train_end = start + window_size
        test_start = train_end + embargo
        test_end = test_start + test_size

        if test_end > n:
            break

        yield (
            np.arange(start, train_end),
            np.arange(test_start, test_end),
        )
        start += step
