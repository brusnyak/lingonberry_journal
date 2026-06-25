"""
Step 3a — Session Range Tracking.

Track per-session O,H,L,C for Asia (00-06), London (06-12), NY (12-24).
Session extremes become liquidity pools for sweep detection.
"""

from __future__ import annotations

from typing import NamedTuple

import pandas as pd


class SessionRange(NamedTuple):
    open: float
    high: float
    low: float
    close: float


SESSION_NAMES = {"asia": (0, 6), "london": (6, 12), "ny": (12, 24)}


def session_ranges(
    ohlc: pd.DataFrame,
) -> dict[str, pd.Series]:
    """
    Compute rolling session O,H,L,C for the current trading day.

    Parameters
    ----------
    ohlc : pd.DataFrame
        5m OHLC data with DatetimeIndex.

    Returns
    -------
    dict of str -> pd.Series
        Each series indexed by candle time, with the current session's
        open, high, low, close columns.
        Keys: "asia", "london", "ny"
    """
    result = {}
    for name, (start_h, end_h) in SESSION_NAMES.items():
        # Build session data per-day
        sessions = []
        indices = []
        for day, group in ohlc.groupby(ohlc.index.date):
            # Filter to this session's hours
            if end_h == 24:
                mask = group.index.hour >= start_h
            else:
                mask = (group.index.hour >= start_h) & (group.index.hour < end_h)

            sess = group[mask]
            if len(sess) == 0:
                continue

            o = sess.iloc[0]["open"]
            h = sess["high"].max()
            l = sess["low"].min()
            c = sess.iloc[-1]["close"]

            # Fill every candle in the session with the same range
            for idx in sess.index:
                sessions.append({"session_open": o, "session_high": h, "session_low": l, "session_close": c})
                indices.append(idx)

        s = pd.DataFrame(sessions, index=pd.DatetimeIndex(indices))
        result[name] = s

    return result


def previous_session_extremes(
    ohlc: pd.DataFrame,
    session_name: str,
) -> tuple[float | None, float | None]:
    """
    Get the previous day's high/low for a given session.

    Returns (prev_session_high, prev_session_low) or (None, None).
    """
    dates = sorted(set(ohlc.index.date))
    if len(dates) < 2:
        return None, None

    prev_date = dates[-2]
    start_h, end_h = SESSION_NAMES[session_name]

    mask = ohlc.index.date == prev_date
    if end_h == 24:
        hour_mask = ohlc.index.hour >= start_h
    else:
        hour_mask = (ohlc.index.hour >= start_h) & (ohlc.index.hour < end_h)

    prev = ohlc[mask & hour_mask]
    if len(prev) == 0:
        return None, None

    return float(prev["high"].max()), float(prev["low"].min())


def prior_day_range(ohlc: pd.DataFrame) -> tuple[float | None, float | None]:
    """Return previous trading day's high and low."""
    dates = sorted(set(ohlc.index.date))
    if len(dates) < 2:
        return None, None

    prev = ohlc[ohlc.index.date == dates[-2]]
    if len(prev) == 0:
        return None, None

    return float(prev["high"].max()), float(prev["low"].min())
