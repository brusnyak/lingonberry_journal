from __future__ import annotations

import pandas as pd

from backtesting.crypto.session_discovery_packet import (
    DiscoveryPacketConfig,
    monday_week_start,
    mode_or_missing,
    parse_csv,
    parse_weeks,
    select_review_windows,
    summarize_sessions,
)
from backtesting.crypto.simple_setup_lab import session_bucket


def _bars() -> pd.DataFrame:
    ts = pd.date_range("2026-01-04", periods=12 * 24, freq="1h", tz="UTC")
    close = pd.Series(range(len(ts)), dtype=float) + 100.0
    return pd.DataFrame(
        {
            "ts": ts,
            "day": ts.floor("D"),
            "week_start": monday_week_start(pd.Series(ts)),
            "session_utc": [session_bucket(t) for t in ts],
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close + 0.25,
            "volume": 1.0,
            "atr": 2.0,
            "regime": ["bull"] * len(ts),
            "bos_up": [False] * len(ts),
            "bos_down": [False] * len(ts),
            "choch_up": [False] * len(ts),
            "choch_down": [False] * len(ts),
            "sweep_high": [False] * len(ts),
            "sweep_low": [False] * len(ts),
        }
    )


def test_select_review_windows_keeps_requested_week_plus_context():
    bars = _bars()
    cfg = DiscoveryPacketConfig(weeks=(pd.Timestamp("2026-01-06", tz="UTC"),), context_days=1)

    selected = select_review_windows(bars, cfg)

    assert selected["ts"].min() == pd.Timestamp("2026-01-05 00:00:00Z")
    assert selected["ts"].max() == pd.Timestamp("2026-01-13 23:00:00Z")


def test_summarize_sessions_outputs_directional_context():
    bars = _bars().iloc[:24].copy()
    bars.loc[bars["session_utc"].eq("asia"), "bos_up"] = True

    summary = summarize_sessions("ETHUSDT", bars)

    asia = summary[summary["session_utc"].eq("asia")].iloc[0]
    assert asia["symbol"] == "ETHUSDT"
    assert int(asia["bars"]) > 0
    assert int(asia["bos_up"]) > 0
    assert asia["dominant_regime"] == "bull"


def test_parse_helpers():
    assert parse_csv("ETHUSDT,SOLUSDT") == ("ETHUSDT", "SOLUSDT")
    assert parse_weeks("2026-01-05")[0] == pd.Timestamp("2026-01-05", tz="UTC")
    assert mode_or_missing(pd.Series(["bear", "bull", "bull"])) == "bull"
