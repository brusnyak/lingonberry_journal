from __future__ import annotations

import pandas as pd

from backtesting.features.ict_structure import IctStructureConfig, build_ict_structure_index


def _bars(closes: list[float]) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=len(closes), freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "ts": ts,
            "open": closes,
            "high": [c + 0.05 for c in closes],
            "low": [c - 0.05 for c in closes],
            "close": closes,
            "volume": 1,
        }
    )


def test_strict_ict_confirms_bearish_after_bullish_choch_then_ll_lh_bos():
    df = _bars(
        [
            1.0,
            2.0,
            1.5,
            3.0,
            2.2,
            3.5,
            2.8,
            2.0,
            2.5,
            1.7,
            2.1,
            1.4,
            1.2,
        ]
    )
    out = build_ict_structure_index(df, IctStructureConfig(left=1, right=1))

    assert out["bearish_choch"].any()
    assert out["bearish_bos"].any()
    assert out.iloc[-1]["ict_state"] == "bearish"
    assert out.iloc[-1]["direction_bias"] == -1


def test_strict_ict_confirms_bullish_after_bearish_choch_then_hh_hl_bos():
    df = _bars(
        [
            3.0,
            2.0,
            2.5,
            1.5,
            2.0,
            1.0,
            1.4,
            2.1,
            1.7,
            2.4,
            1.9,
            2.8,
            3.0,
        ]
    )
    out = build_ict_structure_index(df, IctStructureConfig(left=1, right=1))

    assert out["bullish_choch"].any()
    assert out["bullish_bos"].any()
    assert out.iloc[-1]["ict_state"] == "bullish"
    assert out.iloc[-1]["direction_bias"] == 1


def test_ict_structure_is_causal_and_exposes_zigzag_level():
    df = _bars([1.0, 2.0, 1.5, 3.0, 2.2])
    out = build_ict_structure_index(df, IctStructureConfig(left=1, right=1))

    assert out.loc[1, "swing_type"] == ""
    assert out.loc[2, "swing_type"] == "high"
    assert out.loc[2, "swing_price"] == 2.05
    assert "zigzag_level" in out.columns
