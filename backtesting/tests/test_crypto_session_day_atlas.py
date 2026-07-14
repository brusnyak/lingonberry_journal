from __future__ import annotations

import pandas as pd

from backtesting.crypto.session_day_atlas import classify_day_path, label_session_days


def _day_bars(closes: list[float]) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=len(closes), freq="15min", tz="UTC")
    opens = [closes[0], *closes[:-1]]
    return pd.DataFrame(
        {
            "ts": ts,
            "open": opens,
            "high": [max(o, c) + 0.1 for o, c in zip(opens, closes)],
            "low": [min(o, c) - 0.1 for o, c in zip(opens, closes)],
            "close": closes,
            "volume": 1.0,
        }
    )


def test_label_session_days_marks_directional_up_day_with_active_context():
    bars = _day_bars([100 + i * 0.2 for i in range(96)])
    combo = ["bull"] * len(bars)

    atlas = label_session_days("SYN", bars, combo)

    assert atlas.iloc[0]["day_path"] == "directional_up"
    assert atlas.iloc[0]["active_context_bars"] == len(bars)


def test_label_session_days_marks_flat_range_without_context():
    bars = _day_bars([100 + (0.1 if i % 2 else -0.1) for i in range(96)])
    combo = ["neutral"] * len(bars)

    atlas = label_session_days("SYN", bars, combo)

    assert atlas.iloc[0]["day_path"] == "range"
    assert atlas.iloc[0]["active_context_bars"] == 0


def test_classify_day_path_marks_sweep_revert():
    asia = {"high": 101.0, "low": 99.0}
    london = {"high": 103.0, "low": 99.5}
    ny = {"high": 102.0, "low": 98.5}

    path = classify_day_path(100.0, 100.1, 5.0, asia, london, ny)

    assert path == "sweep_revert"
