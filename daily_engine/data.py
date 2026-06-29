"""Causal daily data + feature layer (lvl 1 of the exogenous-data engine).

Goal: produce a clean, point-in-time-correct daily DataFrame for ONE FX pair,
combining price with a tiny set of macro features, so we can INSPECT coverage
and sanity BEFORE writing any labels or models.

Why these features (and not CPI/NFP/GDP): the chosen FRED series are market or
policy prices that are NEVER revised, so a plain FRED pull is causal-safe.
Revised macro statistics would need FRED's ALFRED vintage API or they leak
future-revised values into the past (the V2_FOUNDATION mistake). Deferred.

Causality rule: every macro series is lagged PUB_LAG_DAYS (default 1) business
days before alignment, so a decision made at day D's close only ever sees macro
values stamped <= D-1. merge_asof(direction="backward") then carries the last
KNOWN value forward across weekends/holidays. No look-ahead by construction.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "market_data"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

# Market/policy series only — none of these are ever revised.
FRED_SERIES = ["DGS2", "DGS10", "DFF", "ECBDFR", "VIXCLS"]

# Conservative publication lag: FRED stamps a value with the date it REFERS to,
# but publishes it the next business day. Lag so we never use same-day data.
PUB_LAG_DAYS = 1


def _fred_key() -> str:
    key = os.getenv("FRED_API_KEY")
    if not key:  # fall back to .env without importing a dotenv dep
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("FRED_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        raise RuntimeError("FRED_API_KEY not set (env or .env)")
    return key


def load_fred_series(series_id: str, start: str = "2009-01-01") -> pd.Series:
    """Daily FRED series indexed by observation date (NaNs dropped)."""
    r = requests.get(
        FRED_URL,
        params=dict(
            series_id=series_id,
            api_key=_fred_key(),
            file_type="json",
            observation_start=start,
        ),
        timeout=30,
    )
    r.raise_for_status()
    obs = r.json()["observations"]
    s = pd.Series(
        {pd.Timestamp(o["date"]): o["value"] for o in obs}, name=series_id
    )
    s = pd.to_numeric(s, errors="coerce").dropna().sort_index()
    return s


def load_price_daily(symbol: str = "EURUSD") -> pd.DataFrame:
    """Daily OHLC. Native 1440 file if present, else resample the 4H (240) file.

    Daily boundary = UTC calendar date. NY-close (17:00 ET) convention is a
    later refinement; for a coverage-sanity v1 the macro mapping is unaffected.
    """
    native = DATA_DIR / f"{symbol}1440.parquet"
    if native.exists():
        df = pd.read_parquet(native)
        df["date"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None).dt.normalize()
        daily = df.set_index("date")[["open", "high", "low", "close"]]
    else:
        df = pd.read_parquet(DATA_DIR / f"{symbol}240.parquet")
        df["date"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None).dt.normalize()
        daily = df.groupby("date").agg(
            open=("open", "first"), high=("high", "max"),
            low=("low", "min"), close=("close", "last"),
        )
    return daily.sort_index()


def build_dataset(symbol: str = "EURUSD") -> pd.DataFrame:
    """Causal daily price + macro feature matrix for one pair."""
    price = load_price_daily(symbol)

    fred = {sid: load_fred_series(sid) for sid in FRED_SERIES}
    macro = pd.DataFrame(fred).sort_index()
    # Forward-fill across non-trading days, THEN apply the publication lag so
    # every row is knowable strictly before the trading day it aligns to.
    macro = macro.ffill().shift(PUB_LAG_DAYS)

    # --- features (4, all from non-revised series) ---
    feat = pd.DataFrame(index=macro.index)
    feat["rate_diff"] = macro["DFF"] - macro["ECBDFR"]      # policy carry
    feat["us2y_mom"] = macro["DGS2"] - macro["DGS2"].shift(20)  # ~1m rate repricing
    feat["slope"] = macro["DGS10"] - macro["DGS2"]          # curve / risk regime
    feat["vix"] = macro["VIXCLS"]                            # risk-on/off
    feat = feat.dropna()

    # Align macro onto trading days: each day gets the last KNOWN macro row.
    out = pd.merge_asof(
        price.reset_index(),
        feat.reset_index().rename(columns={"index": "date"}),
        on="date",
        direction="backward",
    ).set_index("date")
    return out


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    ds = build_dataset(sym)
    print(f"\n=== {sym} daily dataset ===")
    print(f"rows: {len(ds)}   span: {ds.index.min().date()} -> {ds.index.max().date()}")
    print(f"\nNaN counts:\n{ds.isna().sum()}")
    print(f"\nfeature describe:\n{ds[['rate_diff','us2y_mom','slope','vix']].describe().round(3)}")
    print(f"\nhead:\n{ds.head(3)}")
    print(f"\ntail:\n{ds.tail(3)}")
