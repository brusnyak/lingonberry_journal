"""
Tests for the crypto pair screener.

Verifies:
  - screen_pairs returns correct columns and pair count
  - rank_pairs produces sorted output with score
  - Edge cases: empty data, custom weights, top_n
"""

from __future__ import annotations

import pandas as pd
import pytest

from backtesting.crypto.screener import screen_pairs, rank_pairs


class TestScreenPairs:
    def test_returns_all_available_pairs(self):
        """screen_pairs should return all crypto pairs we have data for."""
        df = screen_pairs(tf="60", days=7)
        assert isinstance(df, pd.DataFrame)
        assert len(df) >= 14  # at least the top-14 exchange pairs
        assert "pair" in df.columns
        assert "volatility" in df.columns
        assert "avg_daily_volume" in df.columns
        assert "directional_ratio" in df.columns

    def test_required_columns_present(self):
        df = screen_pairs(tf="60", days=7)
        required = ["pair", "price", "volatility", "avg_daily_volume",
                     "avg_daily_range_pct", "directional_ratio"]
        for col in required:
            assert col in df.columns, f"Missing column: {col}"

    def test_no_duplicate_pairs(self):
        df = screen_pairs(tf="60", days=7)
        assert df["pair"].is_unique

    def test_min_days_filters(self):
        df = screen_pairs(tf="60", days=7, min_days=100)
        assert len(df) == 0

    def test_sorted_by_pair(self):
        df = screen_pairs(tf="60", days=7)
        assert df["pair"].is_monotonic_increasing


class TestRankPairs:
    def test_ranked_has_score_column(self):
        raw = screen_pairs(tf="60", days=7)
        ranked = rank_pairs(raw)
        assert "score" in ranked.columns
        assert 0.0 <= ranked["score"].min() <= 1.0
        assert 0.0 <= ranked["score"].max() <= 1.0

    def test_sorted_descending(self):
        raw = screen_pairs(tf="60", days=7)
        ranked = rank_pairs(raw)
        assert ranked["score"].is_monotonic_decreasing

    def test_top_n(self):
        raw = screen_pairs(tf="60", days=7)
        ranked = rank_pairs(raw, top_n=3)
        assert len(ranked) == 3

    def test_empty_input(self):
        empty = pd.DataFrame()
        result = rank_pairs(empty)
        assert result.empty

    def test_custom_weights(self):
        raw = screen_pairs(tf="60", days=7)
        ranked = rank_pairs(raw, weights={"volatility": 1.0})
        assert len(ranked) == len(raw)
        # First row should be the most volatile pair
        assert ranked.iloc[0]["volatility"] == raw["volatility"].max()

    def test_negative_weight_penalizes(self):
        raw = screen_pairs(tf="60", days=7)
        # Rank by LOW volatility
        ranked = rank_pairs(raw, weights={"volatility": -1.0})
        assert ranked.iloc[0]["volatility"] == raw["volatility"].min()
