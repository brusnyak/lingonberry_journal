from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.portfolio.cross_pair_book import (
    assert_no_position_overlap,
    merge_cross_pair_trades,
)


def _trades(rows):
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "pnl"])


def test_no_overlap_passes():
    a = _trades([("2026-01-01 00:00", "2026-01-01 01:00", 1.0)])
    b = _trades([("2026-01-01 02:00", "2026-01-01 03:00", 2.0)])
    assert_no_position_overlap(a, b)  # should not raise


def test_overlap_raises():
    a = _trades([("2026-01-01 00:00", "2026-01-01 02:00", 1.0)])
    b = _trades([("2026-01-01 01:00", "2026-01-01 03:00", 2.0)])
    with pytest.raises(ValueError, match="Position overlap"):
        assert_no_position_overlap(a, b)


def test_empty_logs_never_overlap():
    a = _trades([])
    b = _trades([("2026-01-01 00:00", "2026-01-01 01:00", 1.0)])
    assert_no_position_overlap(a, b)  # should not raise


def test_merge_sorts_chronologically():
    a = _trades([("2026-01-02 00:00", "2026-01-02 01:00", 1.0)])
    b = _trades([("2026-01-01 00:00", "2026-01-01 01:00", 2.0)])
    merged = merge_cross_pair_trades(a, b)
    assert len(merged) == 2
    assert merged.iloc[0]["pnl"] == 2.0
    assert merged.iloc[1]["pnl"] == 1.0


def test_merge_raises_on_overlap():
    a = _trades([("2026-01-01 00:00", "2026-01-01 02:00", 1.0)])
    b = _trades([("2026-01-01 01:00", "2026-01-01 03:00", 2.0)])
    with pytest.raises(ValueError):
        merge_cross_pair_trades(a, b)


def test_merge_all_empty_returns_empty_df():
    a = _trades([])
    b = _trades([])
    merged = merge_cross_pair_trades(a, b)
    assert merged.empty
