"""
Unified data loader for all assets.

Loads OHLCV from any source with a single function call.
Handles all file formats currently in the project:

  - Flat parquet:   data/market_data/{SYMBOL}{TF}.parquet       (21 forex pairs)
  - Crypto parquet: data/market_data/crypto/{exchange}/{SYMBOL}{TF}.parquet
  - Legacy crypto:  data/market_data/crypto/{SYMBOL}{TF}.parquet
  - Forex CSVs:     data/market_data/forex/{SYMBOL}/m{tf}.csv
  - Index CSVs:     data/market_data/index/{SYMBOL}/{SYMBOL}{tf}.csv
  - Commodity CSVs: data/market_data/commodity/{SYMBOL}/*.csv

Usage:
    from backtesting.engine.data import load_data, list_pairs, list_tfs

    df = load_data("EURUSD", tf="1", days=30)
    df = load_data("BTCUSDT", tf="60", start="2026-01-01", end="2026-06-01", asset_type="crypto", exchange="binance")
    df = load_data("XAUUSD", tf="15", days=90)

    pairs = list_pairs()           # all available symbols
    crypto = list_pairs("crypto")  # crypto only
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "market_data"

# Crypto loading lives in backtesting.crypto.data for a clean separation.
from backtesting.crypto.data import CRYPTO_EXCHANGES, _load_from_crypto_dir, _load_from_crypto_funding, load_funding_rate  # noqa: F401


# ── Helpers ──────────────────────────────────────────────────────────────────


def _parse_ts(ts_str: str) -> pd.Timestamp:
    return pd.Timestamp(ts_str).tz_convert("UTC") if "tz" in str(type(ts_str)) else pd.Timestamp(ts_str, tz="UTC")


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
    """Keep last N days of data."""
    if df.empty or days <= 0:
        return df
    ts_col = "ts" if "ts" in df.columns else df.index.name
    if ts_col:
        cutoff = df[ts_col].max() - timedelta(days=days)
        df = df[df[ts_col] >= cutoff].reset_index(drop=True)
    return df


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

    # Rename common alternatives
    rename = {
        "time": "ts",
        "timestamp": "ts",
        "date": "ts",
        "datetime": "ts",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "vol": "volume",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    required = ["ts", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return pd.DataFrame()

    # Parse timestamps — ensure tz-aware UTC
    if not pd.api.types.is_datetime64_any_dtype(df["ts"]):
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    elif df["ts"].dt.tz is None:
        df["ts"] = df["ts"].dt.tz_localize("UTC")

    # Ensure numeric types
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("ts").reset_index(drop=True)
    cols = ["ts", "open", "high", "low", "close"]
    if "volume" in df.columns:
        cols.append("volume")
    return df[cols].dropna(subset=["ts"])


# ── Loaders for each source ──────────────────────────────────────────────────


CTRADER_DIR = DATA_DIR / "ctrader"


def _load_from_flat_parquet(symbol: str, tf: str) -> pd.DataFrame:
    """Merge data/market_data + pine-review forex/metals + ctrader for maximum history."""
    paths = [
        DATA_DIR / f"{symbol}{tf}.parquet",
        PINE_REVIEW_DIR / "forex"  / f"{symbol}{tf}.parquet",
        PINE_REVIEW_DIR / "metals" / f"{symbol}{tf}.parquet",
        CTRADER_DIR / f"{symbol}{tf}.parquet",
    ]
    frames = []
    for path in paths:
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            if not df.empty:
                frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return frames[0]
    # Normalize each frame individually (may have 'datetime' vs 'ts'), then merge
    normed = [_normalize_columns(f) for f in frames]
    normed = [f for f in normed if not f.empty]
    if not normed:
        return pd.DataFrame()
    if len(normed) == 1:
        return normed[0]
    merged = pd.concat(normed, ignore_index=True)
    merged = merged.drop_duplicates(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    return merged


def _load_from_forex_dir(symbol: str, tf: str) -> pd.DataFrame:
    """data/market_data/forex/{SYMBOL}/m{tf}.csv (or h{tf}, d{tf})"""
    # Map TF to file prefix
    tf_map = {
        "1": ["m1"], "5": ["m5"], "15": ["m15"], "30": ["m30"],
        "60": ["h1"], "240": ["h4"], "1440": ["d1", "d"],
    }
    prefixes = tf_map.get(tf)
    if not prefixes:
        return pd.DataFrame()

    # Try .csv and .parquet
    for prefix in prefixes:
        for ext in [".csv", ".parquet"]:
            path = DATA_DIR / "forex" / symbol / f"{prefix}{ext}"
            if path.exists():
                try:
                    if ext == ".parquet":
                        return pd.read_parquet(path)
                    return pd.read_csv(path)
                except Exception:
                    continue
    return pd.DataFrame()


PINE_REVIEW_DIR = Path(__file__).resolve().parent.parent.parent / "pine-review" / "data" / "parquet"


def _load_from_index_dir(symbol: str, tf: str) -> pd.DataFrame:
    """data/market_data/index/{SYMBOL}/{SYMBOL}{tf}.csv or pine-review/data/parquet/indeces/{SYMBOL}{tf}.parquet"""
    # Try pine-review parquet first (has NAS100, SPX, DJI data)
    pine_path = PINE_REVIEW_DIR / "indeces" / f"{symbol}{tf}.parquet"
    if pine_path.exists():
        try:
            return pd.read_parquet(pine_path)
        except Exception:
            pass

    parquet_path = DATA_DIR / "index" / symbol / f"{symbol}{tf}.parquet"
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except Exception:
            pass

    path = DATA_DIR / "index" / symbol / f"{symbol}{tf}.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(
            path, sep="\t", header=None,
            names=["ts", "open", "high", "low", "close", "volume"],
        )
        return df
    except Exception:
        return pd.DataFrame()


def _load_from_commodity_dir(symbol: str, tf: str) -> pd.DataFrame:
    """data/market_data/commodity/{SYMBOL}/m{tf}.csv (or h{tf})"""
    tf_map = {
        "1": [f"{symbol}1", "m1"],
        "5": [f"{symbol}5", "m5"],
        "15": [f"{symbol}15", "m15"],
        "30": [f"{symbol}30", "m30"],
        "60": [f"{symbol}60", "h1"],
        "240": [f"{symbol}240", "h4"],
        "1440": [f"{symbol}1440", "d", "d1"],
    }
    prefixes = tf_map.get(tf)
    if not prefixes:
        return pd.DataFrame()
    for prefix in prefixes:
        for ext in [".csv", ".parquet"]:
            path = DATA_DIR / "commodity" / symbol / f"{prefix}{ext}"
            if not path.exists():
                continue
            try:
                if ext == ".parquet":
                    return pd.read_parquet(path)
                return pd.read_csv(path)
            except Exception:
                continue
    return pd.DataFrame()


# ── Resampling ───────────────────────────────────────────────────────────────


def _resample_to_tf(df: pd.DataFrame, target_tf: str) -> pd.DataFrame:
    """Resample OHLCV to a higher timeframe."""
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
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna(subset=["open", "high", "low", "close"])
    return resampled.reset_index()[["ts", "open", "high", "low", "close", "volume"]]


# ── Public API ───────────────────────────────────────────────────────────────


def load_data(
    symbol: str,
    tf: str = "60",
    *,
    days: int = 0,
    start: Optional[str | datetime] = None,
    end: Optional[str | datetime] = None,
    asset_type: Optional[str] = None,
    exchange: Optional[str] = None,
    resample: bool = True,
) -> pd.DataFrame:
    """
    Load OHLCV data for any symbol.

    Parameters
    ----------
    symbol : str
        Symbol name, e.g. 'EURUSD', 'BTCUSDT', 'XAUUSD', 'NAS100'.
    tf : str
        Timeframe: '1', '5', '15', '30', '60', '240', '1440'.
    days : int
        Number of recent days to return (0 = all available).
    start : str or datetime, optional
        Start date (overrides days).
    end : str or datetime, optional
        End date (overrides days).
    asset_type : str, optional
        'forex', 'crypto', 'index', 'commodity'.
        If None, auto-detected from symbol and available data.
    exchange : str, optional
        Crypto exchange namespace ('binance' or 'bybit'). If omitted, loader
        checks exchange-scoped crypto data first, then legacy flat crypto files.
    resample : bool
        If True and exact TF not available, resample from lower TF.

    Returns
    -------
    pd.DataFrame with columns: ts, open, high, low, close[, volume]
    """
    symbol = symbol.upper()

    # ── Load from best available source ──
    df = pd.DataFrame()

    if asset_type == "crypto":
        df = _load_from_crypto_dir(symbol, tf, exchange=exchange)
        if df.empty:
            # Try resampling from 1m
            df_1m = _load_from_crypto_dir(symbol, "1", exchange=exchange)
            if not df_1m.empty and resample:
                df = _resample_to_tf(df_1m, tf)
    elif asset_type == "forex":
        df = _load_from_flat_parquet(symbol, tf)
        if df.empty:
            df = _load_from_forex_dir(symbol, tf)
        if df.empty and resample:
            # Try resampling from lower TF
            for lower_tf in ["1", "5", "15", "30"]:
                df_lower = _load_from_flat_parquet(symbol, lower_tf)
                if not df_lower.empty:
                    df = _resample_to_tf(df_lower, tf)
                    if not df.empty:
                        break
    elif asset_type == "index":
        df = _load_from_index_dir(symbol, tf)
        if df.empty and resample:
            df = _load_from_flat_parquet(symbol, tf)  # some indices are in flat parquet
    elif asset_type == "commodity":
        df = _load_from_commodity_dir(symbol, tf)
        if df.empty:
            df = _load_from_flat_parquet(symbol, tf)
        if df.empty and resample:
            df_1m = _load_from_commodity_dir(symbol, "1")
            if df_1m.empty:
                df_1m = _load_from_flat_parquet(symbol, "1")
            if df_1m.empty:
                df_1m = _load_from_commodity_dir(symbol, "5")
            if df_1m.empty:
                df_1m = _load_from_flat_parquet(symbol, "5")
            if not df_1m.empty:
                df = _resample_to_tf(df_1m, tf)
    else:
        # Auto-detect: try each source in order
        for loader in [
            lambda: _load_from_flat_parquet(symbol, tf),
            lambda: _load_from_crypto_dir(symbol, tf, exchange=exchange),
            lambda: _load_from_forex_dir(symbol, tf),
            lambda: _load_from_index_dir(symbol, tf),
            lambda: _load_from_commodity_dir(symbol, tf),
        ]:
            df = loader()
            if not df.empty:
                break

        # If still empty, try resampling from 1m
        if df.empty and resample:
            for lower_tf in ["1", "5"]:
                for loader in [
                    lambda: _load_from_flat_parquet(symbol, lower_tf),
                    lambda: _load_from_crypto_dir(symbol, lower_tf, exchange=exchange),
                    lambda: _load_from_commodity_dir(symbol, lower_tf),
                ]:
                    df_lower = loader()
                    if not df_lower.empty:
                        df = _resample_to_tf(df_lower, tf)
                        if not df.empty:
                            break
                if not df.empty:
                    break

    if df.empty:
        return df

    # Normalize
    df = _normalize_columns(df)
    if df.empty:
        return df

    # Date filtering
    if start or end:
        df = _filter_dates(df, start, end)
    elif days > 0:
        df = _slice_days(df, days)

    return df


def list_pairs(asset_type: Optional[str] = None) -> list[str]:
    """List all available trading pairs."""
    pairs: set[str] = set()

    # Flat parquet files (forex)
    for f in DATA_DIR.glob("*.parquet"):
        name = f.stem
        # Strip trailing number (TF)
        while name and name[-1].isdigit():
            name = name[:-1]
        if len(name) >= 3 and not name.endswith("_funding"):
            pairs.add(name)

    # Crypto dir
    if (DATA_DIR / "crypto").exists():
        for ex in CRYPTO_EXCHANGES:
            ex_dir = DATA_DIR / "crypto" / ex
            if not ex_dir.exists():
                continue
            for f in ex_dir.glob("*.parquet"):
                name = f.stem
                if name.endswith("_funding"):
                    continue
                while name and name[-1].isdigit():
                    name = name[:-1]
                if len(name) >= 3:
                    pairs.add(name)
        for f in (DATA_DIR / "crypto").glob("*.parquet"):
            name = f.stem
            if name.endswith("_funding"):
                continue
            while name and name[-1].isdigit():
                name = name[:-1]
            if len(name) >= 3:
                pairs.add(name)

    # Forex dir
    if (DATA_DIR / "forex").exists():
        for d in (DATA_DIR / "forex").iterdir():
            if d.is_dir():
                pairs.add(d.name)

    # Index dir
    if (DATA_DIR / "index").exists():
        for d in (DATA_DIR / "index").iterdir():
            if d.is_dir():
                pairs.add(d.name)

    # Commodity dir
    if (DATA_DIR / "commodity").exists():
        for d in (DATA_DIR / "commodity").iterdir():
            if d.is_dir():
                pairs.add(d.name)

    return sorted(pairs)


def list_tfs(symbol: str) -> list[str]:
    """List available timeframes for a symbol."""
    tfs = []
    for tf in ["1", "5", "15", "30", "60", "240", "1440"]:
        df = load_data(symbol, tf=tf, days=0)
        if not df.empty:
            tfs.append(tf)
    return tfs


def data_info(symbol: str) -> dict:
    """Print summary of available data for a symbol."""
    info = {"symbol": symbol, "tfs": {}}
    for tf in ["1", "5", "15", "30", "60", "240", "1440"]:
        df = load_data(symbol, tf=tf, days=0)
        if not df.empty:
            info["tfs"][tf] = {
                "bars": len(df),
                "start": str(df["ts"].min()),
                "end": str(df["ts"].max()),
                "cols": list(df.columns),
            }
    return info
