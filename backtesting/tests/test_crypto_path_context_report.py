from __future__ import annotations

import pandas as pd

from backtesting.crypto.path_context_report import (
    PathContextConfig,
    build_path_context,
    sample_path_calls,
    score_path_calls,
    summarize_path_scores_by_foundation,
    summarize_path_scores,
)


def _bars(closes: list[float]) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=len(closes), freq="15min", tz="UTC")
    opens = [closes[0], *closes[:-1]]
    return pd.DataFrame({
        "ts": ts,
        "open": opens,
        "high": [max(o, c) + 0.5 for o, c in zip(opens, closes)],
        "low": [min(o, c) - 0.5 for o, c in zip(opens, closes)],
        "close": closes,
        "volume": 1.0,
    })


def test_build_path_context_detects_expansion_up():
    closes = [100.0] * 40 + [101.0, 102.0, 103.0, 104.0]
    bars = _bars(closes)
    cfg = PathContextConfig(lookback_bars=16, expansion_atr=0.8)

    context = build_path_context("SYN", bars, cfg)

    assert "expansion_up" in set(context["path_context"])
    assert context[context["path_context"] == "expansion_up"]["direction"].eq("bull").all()


def test_build_path_context_detects_sweep_reclaim_long():
    closes = [100.0] * 40 + [99.0, 101.0]
    bars = _bars(closes)
    bars.loc[40, "low"] = 97.0
    bars.loc[40, "close"] = 101.0
    bars.loc[40, "open"] = 99.0
    cfg = PathContextConfig(lookback_bars=16, expansion_atr=10.0, sweep_buffer_atr=0.0)

    context = build_path_context("SYN", bars, cfg)

    assert "sweep_reclaim_long" in set(context["path_context"])


def test_build_path_context_detects_compression_without_direction():
    bars = _bars([100.0 + (0.05 if i % 2 else -0.05) for i in range(60)])
    cfg = PathContextConfig(lookback_bars=16, compression_range_atr=5.0)

    context = build_path_context("SYN", bars, cfg)

    compressed = context[context["path_context"] == "compression"]
    assert not compressed.empty
    assert compressed["direction"].eq("none").all()


def test_sample_and_score_path_calls():
    bars = _bars([100.0] * 40 + [101.0, 102.0, 103.0, 104.0, 105.0])
    cfg = PathContextConfig(lookback_bars=16, expansion_atr=0.8, horizons_bars=(4,))
    context = build_path_context("SYN", bars, cfg)
    calls = sample_path_calls(context, sample_mode="events")
    scores = score_path_calls(bars, calls, cfg)
    summary = summarize_path_scores(context, scores)

    assert not calls.empty
    assert not scores.empty
    assert {"path_context", "direction_accuracy"}.issubset(summary.columns)


def test_score_path_calls_can_fade_path_direction():
    bars = _bars([100.0] * 40 + [101.0, 102.0, 103.0, 104.0, 105.0])
    cfg = PathContextConfig(lookback_bars=16, expansion_atr=0.8, horizons_bars=(4,), direction_mode="fade")
    context = build_path_context("SYN", bars, cfg)
    calls = sample_path_calls(context, sample_mode="events")
    scores = score_path_calls(bars, calls, cfg)

    assert not scores.empty
    assert scores["direction_mode"].eq("fade").all()
    assert set(scores["score_direction"]) == {"bear"}


def test_summarize_path_scores_by_foundation_groups_context():
    scores = pd.DataFrame({
        "direction_mode": ["fade", "fade", "fade"],
        "path_context": ["expansion_up", "expansion_up", "expansion_up"],
        "foundation_state": ["range_or_unresolved", "range_or_unresolved", "confirmed_trend"],
        "horizon_bars": [96, 96, 96],
        "outcome": ["win", "loss", "win"],
    })

    out = summarize_path_scores_by_foundation(scores, min_calls=1)

    assert set(out["foundation_state"]) == {"range_or_unresolved", "confirmed_trend"}
    assert out[out["foundation_state"] == "range_or_unresolved"].iloc[0]["direction_accuracy"] == 0.5
