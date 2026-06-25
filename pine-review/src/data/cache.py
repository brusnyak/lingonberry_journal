"""
Simple caching layer for data fetching to reduce API calls.
"""
import sqlite3
import pandas as pd
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from src.utils.logger import setup_logger
from src.config import PROJECT_ROOT

logger = setup_logger(__name__)


class DataCache:
    """SQLite-based cache for OHLCV data."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize data cache.
        
        Args:
            cache_dir: Directory for cache database (default: PROJECT_ROOT/cache)
        """
        if cache_dir is None:
            cache_dir = PROJECT_ROOT / "cache"
        
        cache_dir.mkdir(exist_ok=True)
        self.db_path = cache_dir / "data_cache.db"
        
        self._init_db()
        logger.info(f"Data cache initialized at {self.db_path}")
    
    def _init_db(self):
        """Initialize cache database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                source TEXT NOT NULL,
                data BLOB NOT NULL,
                cached_at TIMESTAMP NOT NULL,
                UNIQUE(symbol, timeframe, source)
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_timeframe 
            ON ohlcv_cache(symbol, timeframe, source)
        """)
        
        conn.commit()
        conn.close()
    
    def get(
        self,
        symbol: str,
        timeframe: str,
        source: str,
        max_age_minutes: int = 5
    ) -> Optional[pd.DataFrame]:
        """
        Get cached data if available and not expired.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            source: Data source name
            max_age_minutes: Maximum age of cache in minutes
        
        Returns:
            Cached DataFrame or None if not found/expired
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT data, cached_at FROM ohlcv_cache
            WHERE symbol = ? AND timeframe = ? AND source = ?
        """, (symbol, timeframe, source))
        
        result = cursor.fetchone()
        conn.close()
        
        if result is None:
            logger.debug(f"Cache miss: {symbol} {timeframe} ({source})")
            return None
        
        data_blob, cached_at_str = result
        cached_at = datetime.fromisoformat(cached_at_str)
        
        # Check if cache is expired
        age = datetime.now() - cached_at
        if age > timedelta(minutes=max_age_minutes):
            logger.debug(f"Cache expired: {symbol} {timeframe} (age={age})")
            return None
        
        # Deserialize DataFrame
        df = pickle.loads(data_blob)
        logger.debug(f"Cache hit: {symbol} {timeframe} ({source})")
        
        return df
    
    def set(
        self,
        symbol: str,
        timeframe: str,
        source: str,
        data: pd.DataFrame
    ):
        """
        Store data in cache.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            source: Data source name
            data: DataFrame to cache
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Serialize DataFrame
        data_blob = pickle.dumps(data)
        cached_at = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO ohlcv_cache (symbol, timeframe, source, data, cached_at)
            VALUES (?, ?, ?, ?, ?)
        """, (symbol, timeframe, source, data_blob, cached_at))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Cached: {symbol} {timeframe} ({source})")
    
    def clear(self, older_than_hours: int = 24):
        """
        Clear old cache entries.
        
        Args:
            older_than_hours: Remove entries older than this many hours
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=older_than_hours)).isoformat()
        
        cursor.execute("""
            DELETE FROM ohlcv_cache WHERE cached_at < ?
        """, (cutoff,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleared {deleted} old cache entries")
    
    def clear_all(self):
        """Clear entire cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM ohlcv_cache")
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleared all cache ({deleted} entries)")
