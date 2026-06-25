from __future__ import annotations

import pandas as pd

from backtesting.features.structure import StructureConfig, build_structure_index


def _bars() -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=9, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "ts": ts,
            "open": [1, 2, 3, 2, 1, 2, 4, 3, 2],
            "high": [1, 2, 5, 2, 1, 2, 6, 3, 2],
            "low": [1, 2, 3, 2, 0, 2, 4, 3, 2],
            "close": [1, 2, 4, 2, 1, 2, 5, 3, 2],
            "volume": 1,
        }
    )


def test_structure_confirmed_at_right_side_not_pivot_bar():
    out = build_structure_index(_bars(), StructureConfig(left=1, right=1))
    # Pivot high at index 2 is confirmed by index 3, then known after index 3 closes.
    assert out.loc[2, "swing_type"] == ""
    assert out.loc[3, "swing_type"] == "high"
    assert out.loc[3, "swing_price"] == 5
    assert out.loc[3, "swing_ts"] == _bars().loc[2, "ts"]
    assert out.loc[3, "known_after_ts"] == _bars().loc[4, "ts"]
    assert out.loc[3, "confirm_ts"] == _bars().loc[4, "ts"]


def test_structure_labels_and_candidate_levels_exist():
    out = build_structure_index(_bars(), StructureConfig(left=1, right=1))
    assert {"HH", "LL"} & set(out["structure_label"])
    assert "regime" in out.columns
    assert "long_structural_sl" in out.columns
    assert "short_structural_sl" in out.columns
    assert "dist_to_long_sl_pct" in out.columns
