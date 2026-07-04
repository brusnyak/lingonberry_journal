"""
Unified data loader for all assets.

Loads OHLCV from any source with a single function call.
Handles all file formats currently in the project:

  - Forex parquet:  data/market_data/forex/parquet/{SYMBOL}{TF}.parquet       (21 forex pairs)
  - Forex CSVs:     data/market_data/forex/csv/{SYMBOL}{TF}.csv
  - Crypto parquet: data/market_data/crypto/{exchange}/{SYMBOL}{TF}.parquet
  - Legacy crypto:  data/market_data/crypto/legacy/{SYMBOL}{TF}.parquet
  - Index parquet:  data/market_data/index/parquet/{SYMBOL}{TF}.parquet
  - Index CSVs:     data/market_data/index/csv/{ALT_NAME}{TF}.csv
  - Commodity pq:   data/market_data/commodity/parquet/{SYMBOL}{TF}.parquet
  - Commodity CSVs: data/market_data/commodity/csv/{SYMBOL}{TF}.csv

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

import logging

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "market_data"

logger = logging.getLogger(__name__)

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
    """Merge forex/parquet + data/parquet forex + ctrader for maximum history."""
    paths = [
        DATA_DIR / "forex" / "parquet" / f"{symbol}{tf}.parquet",
        PARQUET_DIR / "forex"  / f"{symbol}{tf}.parquet",
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
    """data/market_data/forex/csv/{SYMBOL}{TF}.csv"""
    path = DATA_DIR / "forex" / "csv" / f"{symbol}{tf}.csv"
    if path.exists():
        try:
            df = pd.read_csv(path)
            return df
        except Exception:
            pass
    return pd.DataFrame()


PARQUET_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "parquet"


def _load_from_index_dir(symbol: str, tf: str) -> pd.DataFrame:
    """data/market_data/index/parquet/{SYMBOL}{TF}.parquet or data/parquet/indeces/{SYMBOL}{TF}.parquet"""
    # Try index/parquet first (primary source)
    parquet_path = DATA_DIR / "index" / "parquet" / f"{symbol}{tf}.parquet"
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except Exception:
            pass

    # data/parquet indeces (older alternate names: USA*, DEUIDX*, GBRIDX*)
    pine_path = PARQUET_DIR / "indeces" / f"{symbol}{tf}.parquet"
    if pine_path.exists():
        try:
            return pd.read_parquet(pine_path)
        except Exception:
            pass

    # CSV fallback in index/csv/
    csv_path = DATA_DIR / "index" / "csv" / f"{symbol}{tf}.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(
                csv_path, sep="\t", header=None,
                names=["ts", "open", "high", "low", "close", "volume"],
            )
            return df
        except Exception:
            pass
    return pd.DataFrame()


def _load_from_commodity_dir(symbol: str, tf: str) -> pd.DataFrame:
    """data/market_data/commodity/parquet/{SYMBOL}{TF}.parquet or csv fallback."""
    # Try parquet first (converted from CSV)
    parquet_path = DATA_DIR / "commodity" / "parquet" / f"{symbol}{tf}.parquet"
    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except Exception:
            pass

    # Also check data/parquet/metals (older pipeline, column name 'datetime')
    metals_path = PARQUET_DIR / "metals" / f"{symbol}{tf}.parquet"
    if metals_path.exists():
        try:
            return pd.read_parquet(metals_path)
        except Exception:
            pass

    # CSV fallback
    csv_path = DATA_DIR / "commodity" / "csv" / f"{symbol}{tf}.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(
                csv_path, sep="\t", header=None,
                names=["ts", "open", "high", "low", "close", "volume"],
            )
            return df
        except Exception:
            pass
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
    allow_oos: bool = False,
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
        logger.warning("No data found for %s tf=%s (asset_type=%s, exchange=%s)", symbol, tf, asset_type or "auto", exchange or "auto")
        return df

    # Normalize
    df = _normalize_columns(df)
    if df.empty:
        logger.warning("Data for %s tf=%s was empty after column normalization", symbol, tf)
        return df

    # Date filtering
    if start or end:
        df = _filter_dates(df, start, end)
    elif days > 0:
        df = _slice_days(df, days)

    if df.empty:
        logger.warning("Data for %s tf=%s empty after date filter (start=%s end=%s days=%s)", symbol, tf, start, end, days)

    return df


def list_pairs(asset_type: Optional[str] = None) -> list[str]:
    """List all available trading pairs."""
    pairs: set[str] = set()

    def _extract_pairs_from_parquet_dir(dir_path: Path) -> set[str]:
        """Extract unique symbol names from a directory of {SYM}{TF}.parquet files."""
        found: set[str] = set()
        if not dir_path.exists():
            return found
        for f in dir_path.glob("*.parquet"):
            if f.name.endswith("_funding.parquet") or f.name == "market_specs.parquet":
                continue
            name = f.stem
            while name and name[-1].isdigit():
                name = name[:-1]
            if len(name) >= 3:
                found.add(name)
        return found

    # Forex
    pairs |= _extract_pairs_from_parquet_dir(DATA_DIR / "forex" / "parquet")

    # Crypto — exchange-scoped + legacy
    if (DATA_DIR / "crypto").exists():
        for ex in CRYPTO_EXCHANGES:
            pairs |= _extract_pairs_from_parquet_dir(DATA_DIR / "crypto" / ex)
        pairs |= _extract_pairs_from_parquet_dir(DATA_DIR / "crypto" / "legacy")

    # Indices
    pairs |= _extract_pairs_from_parquet_dir(DATA_DIR / "index" / "parquet")

    # Commodities
    pairs |= _extract_pairs_from_parquet_dir(DATA_DIR / "commodity" / "parquet")

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
