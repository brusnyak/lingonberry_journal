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
    resolve_overlapping_trades,
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


def test_resolve_keeps_both_when_no_overlap():
    a = _trades([("2026-01-01 00:00", "2026-01-01 01:00", 1.0)])
    b = _trades([("2026-01-01 02:00", "2026-01-01 03:00", 2.0)])
    kept, dropped = resolve_overlapping_trades(a, b)
    assert dropped == 0
    assert len(kept) == 2


def test_resolve_drops_later_starting_overlap():
    # a opens first and is still "open" (exit 02:00) when b tries to open at 01:00
    a = _trades([("2026-01-01 00:00", "2026-01-01 02:00", 1.0)])
    b = _trades([("2026-01-01 01:00", "2026-01-01 03:00", 2.0)])
    kept, dropped = resolve_overlapping_trades(a, b)
    assert dropped == 1
    assert len(kept) == 1
    assert kept.iloc[0]["pnl"] == 1.0  # a wins, entered first


def test_resolve_no_priority_by_pair_order():
    # b happens to be passed second but entered first -- b should win,
    # proving there's no pair-order priority, only entry-time order.
    a = _trades([("2026-01-01 01:00", "2026-01-01 03:00", 1.0)])
    b = _trades([("2026-01-01 00:00", "2026-01-01 02:00", 2.0)])
    kept, dropped = resolve_overlapping_trades(a, b)
    assert dropped == 1
    assert kept.iloc[0]["pnl"] == 2.0


def test_resolve_three_pairs_chain():
    a = _trades([("2026-01-01 00:00", "2026-01-01 02:00", 1.0)])
    b = _trades([("2026-01-01 01:00", "2026-01-01 03:00", 2.0)])  # overlaps a, dropped
    c = _trades([("2026-01-01 04:00", "2026-01-01 05:00", 3.0)])  # clear of both
    kept, dropped = resolve_overlapping_trades(a, b, c)
    assert dropped == 1
    assert len(kept) == 2
    assert set(kept["pnl"]) == {1.0, 3.0}


def test_resolve_empty_logs_return_empty():
    kept, dropped = resolve_overlapping_trades(_trades([]), _trades([]))
    assert kept.empty
    assert dropped == 0
