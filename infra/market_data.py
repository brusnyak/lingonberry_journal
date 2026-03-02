#!/usr/bin/env python3
"""
Market Data Fetching
Fetches OHLCV data from various sources with caching
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_timeframe_for_asset(asset_type: str) -> str:
    """Get default timeframe for asset type"""
    timeframe_map = {
        "forex": "H1",
        "crypto": "H1",
        "stock": "D",
        "commodity": "H4",
    }
    return timeframe_map.get(asset_type, "H1")


def _get_cache_key(symbol: str, asset_type: str, timeframe: str, start: datetime, end: datetime) -> str:
    """Generate cache key for market data"""
    key_str = f"{symbol}_{asset_type}_{timeframe}_{start.isoformat()}_{end.isoformat()}"
    return hashlib.md5(key_str.encode()).hexdigest()


def _get_cache_path(cache_key: str) -> Path:
    """Get cache file path"""
    return CACHE_DIR / f"{cache_key}.parquet"


def _is_cache_valid(cache_path: Path, ttl_seconds: int) -> bool:
    """Check if cache is still valid"""
    if not cache_path.exists():
        return False
    
    if ttl_seconds == 0:
        return False
    
    cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
    return cache_age < ttl_seconds


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
    cache_path = _get_cache_path(cache_key)
    
    # Check cache
    if _is_cache_valid(cache_path, ttl_seconds):
        try:
            return pd.read_parquet(cache_path)
        except Exception as e:
            print(f"Cache read error: {e}")
    
    # Fetch fresh data
    df = _fetch_ohlcv(symbol, asset_type, timeframe, start, end)
    
    # Save to cache
    if not df.empty and ttl_seconds > 0:
        try:
            df.to_parquet(cache_path, index=False)
        except Exception as e:
            print(f"Cache write error: {e}")
    
    return df


def _fetch_ohlcv(
    symbol: str,
    asset_type: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Fetch OHLCV data from data source"""
    # Placeholder - implement actual data fetching
    # This would integrate with your data provider (e.g., yfinance, ccxt, etc.)
    
    # For now, return empty DataFrame with correct schema
    return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])


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
