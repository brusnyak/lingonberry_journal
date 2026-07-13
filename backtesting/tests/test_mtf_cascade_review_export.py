"""Regression test for the review-UI 100%-win-rate display bug.

Root cause: the webapp's /api/review/ict-events sorts by review_bucket
(best before worst) then truncates to its fetch limit (80). If a symbol's
exported rows exceed that limit and every win is tagged "best", the
truncated view can be 100% wins even though the real win rate is far
lower -- exactly what was observed and reported as a possible
look-ahead-bias symptom, when it was actually a display sampling bug.
"""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.mtf_cascade_review_export import build_cascade_review_packet

REVIEW_UI_FETCH_LIMIT = 80


def test_per_symbol_export_stays_under_review_ui_fetch_limit():
    df = build_cascade_review_packet(["BTCUSDT"], max_rows_per_symbol=75)
    assert not df.empty
    counts = df.groupby("symbol").size()
    assert (counts <= REVIEW_UI_FETCH_LIMIT).all(), counts.to_dict()


def test_review_bucket_does_not_correlate_with_outcome():
    # A constant/neutral review_bucket is required -- if it's derived from
    # win/loss (the original bug), the UI's best-before-worst sort silently
    # drops losers whenever winners alone exceed the fetch limit.
    df = build_cascade_review_packet(["BTCUSDT"], max_rows_per_symbol=75)
    assert df["review_bucket"].nunique() == 1


def test_capped_sample_preserves_both_outcome_classes():
    df = build_cascade_review_packet(["BTCUSDT"], max_rows_per_symbol=75)
    outcomes = df["outcome_1.5r"]
    assert (outcomes > 0).sum() > 0
    assert (outcomes <= 0).sum() > 0
