"""
Base data interface for unified access to different data sources.
"""
from abc import ABC, abstractmethod
from typing import Optional, List
import pandas as pd
from datetime import datetime


class DataSource(ABC):
    """Abstract base class for data sources."""
    
    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT', 'EURUSD')
            timeframe: Timeframe string (e.g., '1m', '5m', '1h', '1d')
            limit: Number of candles to fetch
            since: Start date (optional)
        
        Returns:
            DataFrame with columns: datetime, open, high, low, close, volume
        """
        pass
    
    @abstractmethod
    def get_available_symbols(self) -> List[str]:
        """Get list of available trading symbols."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if data source is available."""
        pass


class DataManager:
    """Unified interface for accessing multiple data sources."""
    
    def __init__(self):
        self.sources = {}
    
    def register_source(self, name: str, source: DataSource):
        """Register a data source."""
        self.sources[name] = source
    
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        source: str = 'auto',
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from specified or auto-detected source.
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string
            source: Source name ('binance', 'yfinance', 'auto')
            limit: Number of candles
            since: Start date
        
        Returns:
            DataFrame with OHLCV data
        """
        if source == 'auto':
            source = self._detect_source(symbol)
        
        if source not in self.sources:
            raise ValueError(f"Unknown data source: {source}")
        
        data_source = self.sources[source]
        
        if not data_source.is_available():
            raise ConnectionError(f"Data source {source} is not available")
        
        return data_source.fetch_ohlcv(symbol, timeframe, limit, since)
    
    def _detect_source(self, symbol: str) -> str:
        """Auto-detect appropriate data source based on symbol."""
        # Crypto pairs (contains /)
        if '/' in symbol:
            return 'binance'
        
        # Forex pairs (6 characters, all uppercase)
        if len(symbol) == 6 and symbol.isupper() and symbol.isalpha():
            return 'yfinance'
        
        # Metals (starts with XAU, XAG)
        if symbol.startswith(('XAU', 'XAG')):
            return 'yfinance'
        
        # Indices (contains 'IDX' or starts with ^)
        if 'IDX' in symbol or symbol.startswith('^'):
            return 'yfinance'
        
        # Default to yfinance for stocks
        return 'yfinance'
