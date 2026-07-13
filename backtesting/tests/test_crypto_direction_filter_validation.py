"""Tests for crypto direction-filter validation helpers."""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.direction_filter_validation import _apply_direction_filter, _verdict


def _trades() -> pd.DataFrame:
    return pd.DataFrame({
        "direction": ["long", "short", "long", "short"],
        "entry_model": ["next_open", "structure_confirmed_next_open", "fvg_ce_retest", "next_open"],
        "confirmation_model": ["none", "latest_bear_regime", "latest_bull_regime", "none"],
        "local_ema_state": ["bullish", "bearish", "bearish", "mixed"],
        "middle_ema_state": ["bullish", "bearish", "bullish", "bearish"],
        "global_ema_state": ["mixed", "bearish", "bullish", "bearish"],
        "ctx_240_regime": ["bull", "bear", "neutral", "bull"],
        "trend_alignment": ["middle_local_ema", "full_trend", "counter_global_or_structure", "counter_global_or_structure"],
    })


def test_confirmed_only_accepts_confirmed_entry_or_confirmation_model():
    out = _apply_direction_filter(_trades(), "confirmed_only")

    assert len(out) == 2
    assert set(out["confirmation_model"]) == {"latest_bear_regime", "latest_bull_regime"}


def test_ema_and_regime_filters_are_direction_aware():
    trades = _trades()

    assert len(_apply_direction_filter(trades, "local_ema_aligned")) == 2
    assert len(_apply_direction_filter(trades, "middle_local_ema_aligned")) == 2
    assert len(_apply_direction_filter(trades, "global_middle_ema_aligned")) == 3
    assert len(_apply_direction_filter(trades, "all_ema_aligned")) == 1
    assert len(_apply_direction_filter(trades, "regime_aligned")) == 2
    assert len(_apply_direction_filter(trades, "full_trend")) == 1


def test_verdict_rejects_sparse_and_promotes_real_improvement():
    sparse = pd.Series({
        "direction_filter": "confirmed_only",
        "accepted": 12,
        "accepted_keep_rate": 0.8,
        "direction_accuracy_delta": 0.2,
        "avg_r_delta": 0.2,
        "bad_entry_rate_delta": -0.1,
    })
    good = sparse.copy()
    good["accepted"] = 40
    good["direction_accuracy_delta"] = 0.06
    good["avg_r_delta"] = 0.01

    assert _verdict(sparse) == "reject_too_sparse"
    assert _verdict(good) == "direction_improver"
