from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.analysis.no_trade_days import find_no_trade_days


def _bars(day: str, opens_closes: list[tuple[float, float]]) -> pd.DataFrame:
    rows = []
    for i, (o, c) in enumerate(opens_closes):
        rows.append({"ts": pd.Timestamp(f"{day} {13+i}:00:00", tz="UTC"),
                     "open": o, "high": max(o, c) + 1, "low": min(o, c) - 1, "close": c})
    return pd.DataFrame(rows)


def test_ranks_no_trade_days_by_range_descending():
    d1 = _bars("2026-01-05", [(100, 110)])   # big up day, NY calendar date shifts w/ tz
    d2 = _bars("2026-01-06", [(100, 101)])   # small day
    entry_df = pd.concat([d1, d2], ignore_index=True)
    trades = pd.DataFrame(columns=["entry_time"])  # no trades at all
    result = find_no_trade_days(entry_df, trades)
    assert len(result) == 2
    assert result.iloc[0]["day_range_pct"] > result.iloc[1]["day_range_pct"]


def test_excludes_days_with_a_trade():
    d1 = _bars("2026-01-05", [(100, 110)])
    entry_df = d1
    trades = pd.DataFrame({"entry_time": [pd.Timestamp("2026-01-05 14:00:00", tz="UTC")]})
    result = find_no_trade_days(entry_df, trades)
    assert len(result) == 0
