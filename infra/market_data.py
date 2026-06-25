#!/usr/bin/env python3
"""
Market Data Fetching
Fetches OHLCV data from various sources with caching and connection pooling
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
from infra.tradelocker_client import (
    TradeLockerError,
    fetch_historical_bars as _fetch_bars_tradelocker,
)

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
    
    # Special mappings for commodities
    if asset_type == "commodity":
        commodity_map = {
            "XAUUSD": "GC=F",  # Gold Futures
            "XAGUSD": "SI=F",  # Silver Futures
            "XPTUSD": "PL=F",  # Platinum Futures
            "XPDUSD": "PA=F",  # Palladium Futures
        }
        if s in commodity_map:
            return commodity_map[s]
            
    # Special mappings for indices
    if asset_type == "index":
        index_map = {
            "US100": "NQ=F",
            "NAS100": "NQ=F",
            "SPX500": "ES=F",
            "US500": "ES=F",
            "US30": "YM=F",
        }
        if s in index_map:
            return index_map[s]
    
    # Forex symbols
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
    asset_type: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    # Look in the unified directory structure: market_data/{asset}/{symbol}/{tf}.csv
    symbol = symbol.upper()
    asset_type = asset_type.lower()
    tf_lower = timeframe.lower()
    
    path = LOCAL_MARKET_DIR / asset_type / symbol / f"{tf_lower}.csv"
    
    # Fallback to root if not found (legacy)
    if not path.exists():
        path = LOCAL_MARKET_DIR / f"{symbol}_{tf_lower}.csv"
    
    # Fallback to 5m if specific timeframe not found
    if not path.exists():
        path = LOCAL_MARKET_DIR / asset_type/ symbol / "5m.csv"
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
    
    # Add indicators for display and snap-capture
    if not df.empty:
        df = _add_indicators(df)
        
    return df


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add EMA (9, 21, 50, 200) and VWAP to the dataframe"""
    if df.empty:
        return df
    
    # EMA Calculations
    for period in [9, 21, 50, 200]:
        df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()
        
    # VWAP Calculation
    # Typical VWAP is cumulative within a day. 
    # For simplicity and multi-day support, we calculate it relative to the start of the current session in the dataframe.
    if "volume" in df.columns and (df["volume"] > 0).any():
        df["tpv"] = (df["high"] + df["low"] + df["close"]) / 3 * df["volume"]
        df["cum_tpv"] = df["tpv"].cumsum()
        df["cum_vol"] = df["volume"].cumsum()
        df["vwap"] = df["cum_tpv"] / df["cum_vol"]
        df.drop(columns=["tpv", "cum_tpv", "cum_vol"], inplace=True)
    else:
        df["vwap"] = df["close"] # Fallback if no volume

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
    # 1) TradeLocker (forex, commodities — live data)
    # 2) local csv
    # 3) yfinance fallback
    
    # Try TradeLocker first for forex and commodities (fast, live)
    if asset_type in ("forex", "commodity"):
        try:
            tl_df = _fetch_ohlcv_tradelocker(symbol=symbol, timeframe=timeframe, start=start, end=end)
            if not tl_df.empty:
                _save_to_market_data(tl_df, symbol, asset_type, timeframe)
                return tl_df
        except TradeLockerError as e:
            print(f"TradeLocker fetch failed: {e}")
    
    # Fallback to local CSV
    local = _fetch_ohlcv_local_csv(symbol=symbol, asset_type=asset_type, timeframe=timeframe, start=start, end=end)
    if not local.empty:
        return local
    
    # Last resort: yfinance
    yf_data = _fetch_ohlcv_yfinance(symbol=symbol, asset_type=asset_type, timeframe=timeframe, start=start, end=end)
    if not yf_data.empty:
        _save_to_market_data(yf_data, symbol, asset_type, timeframe)
    return yf_data


def _fetch_ohlcv_tradelocker(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Fetch OHLCV from TradeLocker and filter by date range."""
    try:
        # Fetch enough bars to cover the date range
        duration = (end - start).total_seconds()
        days = max(int(duration / 86400) + 1, 5)
        limit = max(500, days * 96)  # approx 96 15m bars per day
        
        df = _fetch_bars_tradelocker(symbol=symbol, timeframe=timeframe, limit=limit)
        
        if df.empty:
            return df
        
        # Filter by date range
        mask = (df["ts"] >= start) & (df["ts"] <= end)
        return df[mask].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])


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
