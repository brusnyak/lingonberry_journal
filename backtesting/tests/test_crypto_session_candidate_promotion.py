"""Tests for crypto session candidate promotion helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from backtesting.crypto.session_candidate_promotion import _filter
from backtesting.crypto.trade_forensics import _path_milestones


def test_filter_applies_exact_candidate_columns():
    trades = pd.DataFrame({
        "session_utc": ["london", "london", "late_us"],
        "direction": ["long", "short", "short"],
        "trend_alignment": ["middle_local_ema", "middle_local_ema", "global_middle_ema"],
        "net_r": [1.0, -1.0, 0.5],
    })

    out = _filter(trades, {
        "session_utc": "london",
        "direction": "long",
        "trend_alignment": "middle_local_ema",
    })

    assert len(out) == 1
    assert out.iloc[0]["net_r"] == 1.0


def test_filter_rejects_missing_candidate_column():
    trades = pd.DataFrame({"session_utc": ["london"]})

    with pytest.raises(ValueError, match="Missing filter column"):
        _filter(trades, {"direction": "long"})


def test_path_milestones_are_direction_aware_for_longs():
    post = pd.DataFrame({
        "high": [101.0, 102.1, 103.2],
        "low": [99.4, 100.8, 101.4],
        "close": [100.8, 101.9, 102.8],
    })

    out = _path_milestones(post, direction="long", entry=100.0, stop=99.0, target=103.0, risk=1.0)

    assert out["bars_to_first_adverse_05r"] == 1
    assert out["bars_to_1r"] == 1
    assert out["bars_to_target"] == 3
    assert out["bars_to_stop"] != out["bars_to_stop"]
    assert out["path_mfe_r"] == pytest.approx(3.2)
    assert out["path_mae_r"] == pytest.approx(-0.6)


def test_path_milestones_are_direction_aware_for_shorts():
    post = pd.DataFrame({
        "high": [100.4, 99.3, 98.8],
        "low": [99.0, 97.9, 96.8],
        "close": [99.2, 98.1, 97.2],
    })

    out = _path_milestones(post, direction="short", entry=100.0, stop=101.0, target=97.0, risk=1.0)

    assert out["bars_to_first_adverse_05r"] != out["bars_to_first_adverse_05r"]
    assert out["bars_to_1r"] == 1
    assert out["bars_to_target"] == 3
    assert out["bars_to_stop"] != out["bars_to_stop"]
    assert out["path_mfe_r"] == pytest.approx(3.2)
    assert out["path_mae_r"] == pytest.approx(-0.4)
