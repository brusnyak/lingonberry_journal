"""
Crypto data loading — OHLCV + funding rates from exchange-scoped parquet files.

Entry point is `load_crypto()`. For the unified loader that auto-detects
asset type, use `backtesting.engine.data.load_data()` with `exchange=` param.

Data layout:
  data/market_data/crypto/{exchange}/{SYMBOL}{TF}.parquet
  data/market_data/crypto/{exchange}/{SYMBOL}_funding.parquet
  data/market_data/crypto/{SYMBOL}{TF}.parquet  (legacy flat)

Usage:
    from backtesting.crypto.data import load_crypto, load_funding_rate
    df = load_crypto("BTCUSDT", tf="5", exchange="binance", days=30)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "market_data"
CRYPTO_EXCHANGES = ("binance", "bybit")
PARQUET_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "parquet"


# ── Helpers (duplicated from engine.data for independence) ────────────────────


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure standard column names and types."""
    if len(df.columns) == 1:
        first = str(df.columns[0])
        sample = first if df.empty else str(df.iloc[0, 0])
        if "\t" in first or "\t" in sample:
            rows = [first]
            if not df.empty:
                rows.extend(df.iloc[:, 0].astype(str).tolist())
            split = [row.split("\t") for row in rows if row and row != "nan"]
            df = pd.DataFrame(split, columns=["ts", "open", "high", "low", "close", "volume"])

    rename = {
        "time": "ts", "timestamp": "ts", "date": "ts", "datetime": "ts",
        "open": "open", "high": "high", "low": "low", "close": "close",
        "volume": "volume", "vol": "volume",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    required = ["ts", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return pd.DataFrame()

    if not pd.api.types.is_datetime64_any_dtype(df["ts"]):
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    elif df["ts"].dt.tz is None:
        df["ts"] = df["ts"].dt.tz_localize("UTC")

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("ts").reset_index(drop=True)
    cols = ["ts", "open", "high", "low", "close"]
    if "volume" in df.columns:
        cols.append("volume")
    return df[cols].dropna(subset=["ts"])


def _filter_dates(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    if df.empty:
        return df
    ts_col = "ts" if "ts" in df.columns else df.index.name
    if ts_col is None:
        return df
    mask = pd.Series(True, index=df.index)
    if start:
        start_ts = pd.Timestamp(start, tz="UTC") if isinstance(start, str) else pd.Timestamp(start)
        if start_ts.tzinfo is None:
            start_ts = start_ts.tz_localize("UTC")
        mask &= df[ts_col] >= start_ts
    if end:
        end_ts = pd.Timestamp(end, tz="UTC") if isinstance(end, str) else pd.Timestamp(end)
        if end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize("UTC")
        mask &= df[ts_col] <= end_ts
    return df[mask].reset_index(drop=True)


def _slice_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    if df.empty or days <= 0:
        return df
    ts_col = "ts" if "ts" in df.columns else df.index.name
    if ts_col:
        cutoff = df[ts_col].max() - timedelta(days=days)
        df = df[df[ts_col] >= cutoff].reset_index(drop=True)
    return df


# ── Loaders ───────────────────────────────────────────────────────────────────


def _load_from_crypto_dir(symbol: str, tf: str, exchange: Optional[str] = None) -> pd.DataFrame:
    """
    Merge legacy + exchange-scoped OHLCV for maximum history.

    Legacy has the deepest history (5+ years for most pairs). Exchange-scoped
    files may have more recent bars. We load both and merge (dedup by ts),
    which gives a single DataFrame with the full span: deep past from legacy +
    latest bars from exchange.
    """
    df = pd.DataFrame()

    # 1. Legacy first — deepest history
    legacy_path = DATA_DIR / "crypto" / "legacy" / f"{symbol}{tf}.parquet"
    if legacy_path.exists():
        try:
            df = pd.read_parquet(legacy_path)
        except Exception:
            pass

    # 2. Exchange-scoped — may have more recent bars
    exchange_paths: list[Path] = []
    if exchange:
        exchange_paths.append(DATA_DIR / "crypto" / exchange.lower() / f"{symbol}{tf}.parquet")
    else:
        for ex in CRYPTO_EXCHANGES:
            exchange_paths.append(DATA_DIR / "crypto" / ex / f"{symbol}{tf}.parquet")

    for path in exchange_paths:
        if not path.exists():
            continue
        try:
            exch_df = pd.read_parquet(path)
            if exch_df.empty:
                continue
            # Merge: legacy has older data, exchange has newer data
            df = pd.concat([df, exch_df], ignore_index=True)
        except Exception:
            continue

    # 3. data/parquet/crypto fallback (BTCUSD, ETHUSD, etc.)
    if df.empty:
        old_path = PARQUET_DIR / "crypto" / f"{symbol}{tf}.parquet"
        if old_path.exists():
            try:
                df = pd.read_parquet(old_path)
            except Exception:
                pass

    # Dedup/sort unconditionally -- NOT just as a side effect of merging in an
    # exchange-scoped file above. Bug found 2026-07-12: when no exchange file
    # exists for a symbol/TF (e.g. XRPUSDT30 has no binance/bybit-scoped file,
    # only legacy), this used to skip entirely, so duplicate timestamps already
    # present WITHIN the legacy file (42 found in XRPUSDT30 around 2022-05-13,
    # a real data-source glitch, not caused by the merge) passed straight
    # through unfiltered -- eventually crashing TrIct's `next()` since
    # `df.index.get_loc(ts)` returns a slice instead of a scalar int when the
    # index has duplicate values, and `next()` assumes a scalar.
    if not df.empty:
        df = df.drop_duplicates(subset=["ts"], keep="last")
        df = df.sort_values("ts").reset_index(drop=True)

    return df


def _load_from_crypto_funding(symbol: str, exchange: Optional[str] = None) -> pd.DataFrame:
    """data/market_data/crypto/{exchange}/{SYMBOL}_funding.parquet, with fallback."""
    paths = []
    if exchange:
        paths.append(DATA_DIR / "crypto" / exchange.lower() / f"{symbol}_funding.parquet")
        paths.append(DATA_DIR / "crypto" / "legacy" / f"{symbol}_funding.parquet")
    else:
        for ex in CRYPTO_EXCHANGES:
            paths.append(DATA_DIR / "crypto" / ex / f"{symbol}_funding.parquet")
        paths.append(DATA_DIR / "crypto" / "legacy" / f"{symbol}_funding.parquet")

    for path in paths:
        if not path.exists():
            continue
        try:
            return pd.read_parquet(path)
        except Exception:
            continue
    return pd.DataFrame()


def _load_from_legacy_crypto_dir(symbol: str, tf: str) -> pd.DataFrame:
    """data/market_data/crypto/legacy/{SYMBOL}{TF}.parquet."""
    path = DATA_DIR / "crypto" / "legacy" / f"{symbol}{tf}.parquet"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def _resample_to_tf(df: pd.DataFrame, target_tf: str) -> pd.DataFrame:
    """Resample OHLCV to a higher timeframe (local copy for independence)."""
    if df.empty or "ts" not in df.columns:
        return df
    rule_map = {
        "1": "1min", "5": "5min", "15": "15min", "30": "30min",
        "60": "1h", "240": "4h", "1440": "1d",
    }
    rule = rule_map.get(target_tf)
    if not rule:
        return df
    df = df.set_index("ts").sort_index()
    resampled = df.resample(rule).agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    }).dropna(subset=["open", "high", "low", "close"])
    return resampled.reset_index()[["ts", "open", "high", "low", "close", "volume"]]


# ── Public API ────────────────────────────────────────────────────────────────


def load_crypto(
    symbol: str,
    tf: str = "60",
    *,
    days: int = 0,
    start: Optional[str | datetime] = None,
    end: Optional[str | datetime] = None,
    exchange: Optional[str] = None,
    resample: bool = True,
) -> pd.DataFrame:
    """
    Load OHLCV data for a crypto futures symbol.

    Parameters
    ----------
    symbol : str    — e.g. 'BTCUSDT', 'DOGEUSDT', '1000PEPEUSDT'
    tf : str        — '1', '5', '15', '30', '60', '240', '1440'
    days : int      — recent N days (0 = all)
    start / end     — date range override
    exchange        — 'binance', 'bybit', or None to try both
    resample        — fall back to resampling from 1m if exact TF missing
    """
    symbol = symbol.upper()
    df = _load_from_crypto_dir(symbol, tf, exchange=exchange)
    if df.empty and resample:
        df_1m = _load_from_crypto_dir(symbol, "1", exchange=exchange)
        if not df_1m.empty:
            df = _resample_to_tf(df_1m, tf)

    if df.empty:
        return df

    df = _normalize_columns(df)
    if df.empty:
        return df

    if start or end:
        df = _filter_dates(df, start, end)
    elif days > 0:
        df = _slice_days(df, days)

    return df


def load_funding_rate(symbol: str, exchange: Optional[str] = None) -> pd.DataFrame:
    """Load funding rate data for a crypto symbol.

    Returns DataFrame with columns: ts, fundingRate
    """
    df = _load_from_crypto_funding(symbol, exchange=exchange)
    if df.empty:
        return df
    if not pd.api.types.is_datetime64_any_dtype(df["ts"]):
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    return df.dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)


def load_market_specs(symbol: str, exchange: str) -> dict:
    """Load latest exchange market specs (min_notional, min_qty, qty_step,
    tick_size) for a pair. Moved here from batch.py (was private/duplicated
    logic) so pair-feasibility checks and cost-model wiring share one
    source instead of drifting apart.
    """
    spec_path = DATA_DIR / "crypto" / exchange.lower() / "market_specs.parquet"
    if not spec_path.exists():
        return {}
    try:
        specs = pd.read_parquet(spec_path)
        pair_specs = specs[specs["id"] == symbol.upper()]
        if pair_specs.empty:
            return {}
        latest = pair_specs.sort_values("ts").iloc[-1]
        return {
            "min_notional": float(latest.get("min_notional", 0) or 0),
            "min_qty": float(latest.get("min_qty", 0) or 0),
            "qty_step": float(latest.get("amount_precision", 0) or 0),
            "tick_size": float(latest.get("price_precision", 0) or 0),
        }
    except Exception:
        return {}
