"""
Finds calendar days in the backtest window where a strategy took NO trade,
ranked by how much the day actually trended -- so a manual review can
prioritize days that look like they should have produced a signal but
didn't, instead of scanning the whole dataset blind.

Reuses the same engine.runner.run() as every other backtest here; this
only adds the "which days got skipped, and were they good days" question.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def find_no_trade_days(entry_df: pd.DataFrame, trades: pd.DataFrame,
                       session_tz: str = "America/New_York") -> pd.DataFrame:
    """
    entry_df: the raw entry-timeframe OHLC data the strategy ran on
               (e.g. the 5m NAS100 DataFrame passed into run()).
    trades:   trades DataFrame from result.to_df().
    Returns a DataFrame, one row per no-trade day, sorted by day_range_pct
    descending (biggest trending days with no trade first).
    """
    df = entry_df.copy()
    ts = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(session_tz)
    df["date"] = ts.dt.date

    daily = df.groupby("date").agg(
        day_open=("open", "first"), day_high=("high", "max"),
        day_low=("low", "min"), day_close=("close", "last"),
    )
    daily["day_range_pct"] = (daily["day_high"] - daily["day_low"]) / daily["day_open"] * 100
    daily["day_move_pct"] = (daily["day_close"] - daily["day_open"]) / daily["day_open"] * 100
    daily["direction"] = np.where(daily["day_move_pct"] > 0, "up", "down")

    traded_dates = set()
    if len(trades) > 0:
        tr = trades.copy()
        tr_ts = pd.to_datetime(tr["entry_time"], utc=True).dt.tz_convert(session_tz)
        traded_dates = set(tr_ts.dt.date)

    daily["traded"] = daily.index.isin(traded_dates)
    no_trade = daily[~daily["traded"]].drop(columns=["traded"]).sort_values("day_range_pct", ascending=False)
    return no_trade
