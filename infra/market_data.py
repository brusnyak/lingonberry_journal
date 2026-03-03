#!/usr/bin/env python3
"""
Market Data Fetching
Fetches OHLCV data from various sources with caching
"""
import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from infra.ctrader_client import CTraderClient

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_MARKET_DIR = Path("data/market_data")


def get_timeframe_for_asset(asset_type: str) -> str:
    """Get default timeframe for asset type"""
    timeframe_map = {
        "forex": "H1",
        "crypto": "H1",
        "stock": "D",
        "commodity": "H4",
    }
    return timeframe_map.get(asset_type, "H1")


def _to_yf_symbol(symbol: str, asset_type: str) -> str:
    s = (symbol or "").upper().strip()
    if asset_type == "forex":
        # Remove any existing suffix
        s = s.replace("=X", "").replace("/", "")
        if len(s) == 6:
            # Format as BASE/QUOTE for yfinance
            return f"{s[:3]}{s[3:]}=X"
    return s


def _to_yf_interval(timeframe: str) -> str:
    mapping = {
        "M1": "1m",
        "M5": "5m",
        "M15": "15m",
        "M30": "30m",
        "H1": "60m",
        "H4": "1h",
        "D": "1d",
        "W": "1wk",
    }
    return mapping.get(timeframe.upper(), "15m")


def _fetch_ohlcv_yfinance(
    symbol: str,
    asset_type: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    try:
        yf_symbol = _to_yf_symbol(symbol, asset_type)
        interval = _to_yf_interval(timeframe)
        data = yf.download(
            yf_symbol,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=False,
            progress=False,
        )
        if data is None or data.empty:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

        data = data.rename(columns=str.lower).reset_index()
        ts_col = "Datetime" if "Datetime" in data.columns else "Date"
        data["ts"] = pd.to_datetime(data[ts_col], utc=True, errors="coerce")
        out = data[["ts", "open", "high", "low", "close", "volume"]].dropna(subset=["ts"]).copy()
        return out.sort_values("ts").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])


def _fetch_ohlcv_ctrader(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    tf = timeframe.upper()
    tf_map = {
        "M1": "M1",
        "M5": "M5",
        "M15": "M15",
        "M30": "M30",
        "H1": "H1",
        "H4": "H4",
        "D": "D1",
    }
    period = tf_map.get(tf, "M15")
    try:
        client = CTraderClient()
        if not client.connect():
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        bars = client.get_trendbars(symbol=symbol, timeframe=period, from_ts=start, to_ts=end, count=2000)
        client.disconnect()
        if not bars:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        df = pd.DataFrame(bars)
        # cTrader payload keys can differ by endpoint/account; normalize defensively.
        ts_col = "timestamp" if "timestamp" in df.columns else "time"
        df["ts"] = pd.to_datetime(df[ts_col], unit="ms", utc=True, errors="coerce")
        col_map = {
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "openPrice": "open",
            "highPrice": "high",
            "lowPrice": "low",
            "closePrice": "close",
        }
        for src, dst in col_map.items():
            if src in df.columns and dst not in df.columns:
                df[dst] = df[src]
        if "volume" not in df.columns:
            df["volume"] = 0.0
        out = df[["ts", "open", "high", "low", "close", "volume"]].dropna(subset=["ts"])
        return out.sort_values("ts").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])


def _resample_ohlcv(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    tf = timeframe.upper()
    if tf in {"M5", "5M"}:
        return df
    rule_map = {
        "M1": "1min",
        "M15": "15min",
        "M30": "30min",
        "H1": "1H",
        "H4": "4H",
        "D": "1D",
        "D1": "1D",
    }
    rule = rule_map.get(tf)
    if not rule:
        return df

    frame = df.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["ts"]).set_index("ts").sort_index()
    resampled = frame.resample(rule).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    resampled = resampled.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return resampled[["ts", "open", "high", "low", "close", "volume"]]


def _fetch_ohlcv_local_csv(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    # Try to find cached file for this timeframe
    tf_lower = timeframe.lower()
    path = LOCAL_MARKET_DIR / f"{symbol.upper()}_{tf_lower}.csv"
    
    # Fallback to 5m data if specific timeframe not found
    if not path.exists():
        path = LOCAL_MARKET_DIR / f"{symbol.upper()}_5m.csv"
    
    if not path.exists():
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
    try:
        df = pd.read_csv(path)
        ts_col = "ts" if "ts" in df.columns else "time" if "time" in df.columns else None
        if not ts_col:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
        cols = ["open", "high", "low", "close", "volume"]
        for col in cols:
            if col not in df.columns:
                return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        base = df[["ts", "open", "high", "low", "close", "volume"]].dropna(subset=["ts"]).sort_values("ts")
        filtered = base[(base["ts"] >= start) & (base["ts"] <= end)]
        return _resample_ohlcv(filtered, timeframe)
    except Exception:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])


def _get_cache_key(symbol: str, asset_type: str, timeframe: str, start: datetime, end: datetime) -> str:
    """Generate cache key for market data"""
    key_str = f"{symbol}_{asset_type}_{timeframe}_{start.isoformat()}_{end.isoformat()}"
    return hashlib.md5(key_str.encode()).hexdigest()


def _get_cache_path(cache_key: str) -> Path:
    """Get cache file path"""
    return CACHE_DIR / f"{cache_key}.parquet"


def _get_cache_csv_path(cache_key: str) -> Path:
    """Get CSV fallback cache path when parquet engine is unavailable."""
    return CACHE_DIR / f"{cache_key}.csv"


def _is_cache_valid(cache_path: Path, ttl_seconds: int) -> bool:
    """Check if cache is still valid"""
    if not cache_path.exists():
        return False
    
    if ttl_seconds == 0:
        return False
    
    cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
    return cache_age < ttl_seconds


def _read_cached_frame(cache_key: str, ttl_seconds: int) -> Optional[pd.DataFrame]:
    parquet_path = _get_cache_path(cache_key)
    csv_path = _get_cache_csv_path(cache_key)

    if _is_cache_valid(parquet_path, ttl_seconds):
        try:
            return pd.read_parquet(parquet_path)
        except Exception as e:
            print(f"Cache parquet read error: {e}")

    if _is_cache_valid(csv_path, ttl_seconds):
        try:
            df = pd.read_csv(csv_path)
            if "ts" in df.columns:
                df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
            return df
        except Exception as e:
            print(f"Cache CSV read error: {e}")

    return None


def _write_cached_frame(cache_key: str, df: pd.DataFrame) -> None:
    parquet_path = _get_cache_path(cache_key)
    csv_path = _get_cache_csv_path(cache_key)
    try:
        df.to_parquet(parquet_path, index=False)
        return
    except Exception:
        pass
    try:
        df.to_csv(csv_path, index=False)
    except Exception as e:
        print(f"Cache write error: {e}")


def load_ohlcv_with_cache(
    symbol: str,
    asset_type: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    ttl_seconds: int = 3600,
) -> pd.DataFrame:
    """
    Load OHLCV data with caching
    
    Args:
        symbol: Trading symbol
        asset_type: Asset type (forex, crypto, stock, commodity)
        timeframe: Timeframe (M1, M5, M15, H1, H4, D)
        start: Start datetime
        end: End datetime
        ttl_seconds: Cache TTL in seconds (0 = no cache)
    
    Returns:
        DataFrame with columns: ts, open, high, low, close, volume
    """
    cache_key = _get_cache_key(symbol, asset_type, timeframe, start, end)
    cached = _read_cached_frame(cache_key, ttl_seconds)
    if cached is not None:
        return cached
    
    # Fetch fresh data
    df = _fetch_ohlcv(symbol, asset_type, timeframe, start, end)
    
    # Save to cache
    if not df.empty and ttl_seconds > 0:
        _write_cached_frame(cache_key, df)
    
    return df


def _fetch_ohlcv(
    symbol: str,
    asset_type: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Fetch OHLCV data from data source with fallback chain."""
    # Priority:
    # 1) cTrader (forex only, when credentials + SDK are available)
    # 2) local csv
    # 3) yfinance fallback
    if asset_type.lower() == "forex":
        ctr = _fetch_ohlcv_ctrader(symbol=symbol, timeframe=timeframe, start=start, end=end)
        if not ctr.empty:
            # Save to market_data folder
            _save_to_market_data(ctr, symbol, asset_type, timeframe)
            return ctr
    local = _fetch_ohlcv_local_csv(symbol=symbol, timeframe=timeframe, start=start, end=end)
    if not local.empty:
        return local
    yf_data = _fetch_ohlcv_yfinance(symbol=symbol, asset_type=asset_type, timeframe=timeframe, start=start, end=end)
    if not yf_data.empty:
        _save_to_market_data(yf_data, symbol, asset_type, timeframe)
    return yf_data


def _save_to_market_data(df: pd.DataFrame, symbol: str, asset_type: str, timeframe: str) -> None:
    """Save fetched data to market_data folder"""
    if df.empty:
        return
    
    try:
        # Create directory structure: market_data/{asset_type}/{SYMBOL}/
        output_dir = LOCAL_MARKET_DIR / asset_type.lower() / symbol.upper()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save as {timeframe}.csv
        output_path = output_dir / f"{timeframe.lower()}.csv"
        df.to_csv(output_path, index=False)
    except Exception as e:
        print(f"Warning: Could not save to market_data: {e}")


def replay_window(ts_open: str, context_weeks: int = 1) -> Dict[str, datetime]:
    """Calculate replay window for a trade"""
    ts = datetime.fromisoformat(ts_open.replace("Z", "+00:00"))
    
    start = ts - timedelta(weeks=context_weeks)
    end = ts + timedelta(days=1)
    
    return {"start": start, "end": end}


def get_current_price(symbol: str, asset_type: str) -> Optional[float]:
    """Get current price for a symbol"""
    # Placeholder - implement actual price fetching
    return None


def get_symbol_info(symbol: str, asset_type: str) -> Optional[Dict]:
    """Get symbol information"""
    # Placeholder - implement actual symbol info fetching
    return {
        "symbol": symbol,
        "asset_type": asset_type,
        "pip_size": 0.0001 if asset_type == "forex" else 0.01,
        "contract_size": 100000 if asset_type == "forex" else 1,
    }
