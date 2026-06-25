"""
Unified data loader for CSV and Parquet files.
"""
import pandas as pd
import os
from typing import Optional
from datetime import datetime, timedelta


class DataLoader:
    """Load market data from CSV or Parquet files."""
    
    def __init__(self, data_dir: str = 'data'):
        self.data_dir = data_dir
        self.csv_dir = os.path.join(data_dir, 'charts')
        self.parquet_dir = os.path.join(data_dir, 'parquet')
    
    def load(self, symbol: str, timeframe: str, 
             start_date: Optional[datetime] = None,
             end_date: Optional[datetime] = None,
             limit: Optional[int] = None,
             prefer_parquet: bool = True) -> pd.DataFrame:
        """
        Load data with automatic format detection.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSD', 'EURUSD')
            timeframe: Timeframe (e.g., '1', '5', '15', '60', '240', '1440')
            start_date: Start date filter
            end_date: End date filter
            limit: Max number of bars (takes most recent)
            prefer_parquet: Try parquet first, fallback to CSV
        
        Returns:
            DataFrame with OHLCV data
        """
        # Detect asset type
        asset_type = self._detect_asset_type(symbol)
        
        # Try parquet first if preferred
        if prefer_parquet:
            df = self._load_parquet(symbol, timeframe, asset_type)
            if df is not None:
                return self._filter_data(df, start_date, end_date, limit)
        
        # Fallback to CSV
        df = self._load_csv(symbol, timeframe, asset_type)
        if df is not None:
            return self._filter_data(df, start_date, end_date, limit)
        
        raise FileNotFoundError(f"No data found for {symbol} {timeframe}")
    
    def _detect_asset_type(self, symbol: str) -> str:
        """Detect asset type from symbol."""
        fiat = {'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'NZD', 'CHF'}

        if 'IDX' in symbol:
            return 'indeces'
        if symbol.startswith(('XAU', 'XAG')):
            return 'metals'

        # Forex pairs are 6-letter fiat/fiat symbols (e.g., EURUSD, GBPJPY).
        if len(symbol) == 6:
            base, quote = symbol[:3], symbol[3:]
            if base in fiat and quote in fiat and base != quote:
                return 'forex'

        # Crypto conventions (e.g., BTCUSDT, BTCUSD, ETHUSD, ADAUSDT).
        if 'USDT' in symbol or (symbol.endswith('USD') and len(symbol) <= 10):
            return 'crypto'

        return 'crypto'  # Default
    
    def _load_parquet(self, symbol: str, timeframe: str, asset_type: str) -> Optional[pd.DataFrame]:
        """Load from parquet file."""
        filepath = os.path.join(self.parquet_dir, asset_type, f'{symbol}{timeframe}.parquet')
        
        if not os.path.exists(filepath):
            return None
        
        try:
            df = pd.read_parquet(filepath)
            
            # Ensure datetime index
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.set_index('datetime')
            elif not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            return df
        except Exception as e:
            print(f"Error loading parquet: {e}")
            return None
    
    def _load_csv(self, symbol: str, timeframe: str, asset_type: str) -> Optional[pd.DataFrame]:
        """Load from CSV file."""
        filepath = os.path.join(self.csv_dir, asset_type, f'{symbol}{timeframe}.csv')
        
        if not os.path.exists(filepath):
            return None
        
        try:
            # CSV has no headers, columns are: datetime, open, high, low, close, volume
            df = pd.read_csv(filepath, sep='\s+', header=None,
                           names=['datetime', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
            
            return df
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return None
    
    def _filter_data(self, df: pd.DataFrame, 
                    start_date: Optional[datetime],
                    end_date: Optional[datetime],
                    limit: Optional[int]) -> pd.DataFrame:
        """Filter data by date range and limit."""
        # Date filtering
        if start_date is not None:
            df = df[df.index >= start_date]
        
        if end_date is not None:
            df = df[df.index <= end_date]
        
        # Limit filtering (take most recent)
        if limit is not None and len(df) > limit:
            df = df.iloc[-limit:]
        
        return df
    
    def get_rolling_windows(self, symbol: str, timeframe: str,
                           window_days: int = 60,
                           step_days: int = 30) -> list:
        """
        Get rolling time windows for walk-forward testing.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            window_days: Window size in days
            step_days: Step size in days
        
        Returns:
            List of (start_date, end_date) tuples
        """
        # Load full dataset to get date range
        df = self.load(symbol, timeframe, prefer_parquet=True)
        
        if df is None or len(df) == 0:
            return []
        
        start = df.index.min()
        end = df.index.max()
        
        windows = []
        current_start = start
        
        while current_start < end:
            current_end = current_start + timedelta(days=window_days)
            
            if current_end > end:
                current_end = end
            
            windows.append((current_start, current_end))
            
            current_start += timedelta(days=step_days)
            
            # Stop if we've reached the end
            if current_start >= end:
                break
        
        return windows
