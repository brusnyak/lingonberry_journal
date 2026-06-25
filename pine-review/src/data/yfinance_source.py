"""
Yahoo Finance data source for stocks, forex, metals, indices.
"""
import yfinance as yf
import pandas as pd
from typing import Optional, List
from datetime import datetime, timedelta
from src.data.base import DataSource
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class YFinanceSource(DataSource):
    """Yahoo Finance data source for traditional markets."""
    
    # Timeframe mapping (yfinance uses different notation)
    TIMEFRAME_MAP = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1h',
        '4h': '4h',  # Not directly supported, will use 1h and resample
        '1d': '1d',
        '1w': '1wk',
        '1M': '1mo'
    }
    
    def __init__(self):
        """Initialize Yahoo Finance source."""
        logger.info("Yahoo Finance source initialized")
    
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Yahoo Finance.
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'EURUSD=X', 'GC=F')
            timeframe: Timeframe ('1m', '5m', '1h', '1d', etc.)
            limit: Number of candles
            since: Start datetime
        
        Returns:
            DataFrame with columns: datetime, open, high, low, close, volume
        """
        try:
            # Convert symbol format
            yf_symbol = self._convert_symbol(symbol)
            
            # Map timeframe
            yf_interval = self.TIMEFRAME_MAP.get(timeframe, '1d')
            
            # Calculate period
            if since:
                start_date = since
                end_date = datetime.now()
            else:
                # Estimate period based on limit and timeframe
                period = self._calculate_period(timeframe, limit)
                start_date = datetime.now() - timedelta(days=period)
                end_date = datetime.now()
            
            logger.debug(f"Fetching {yf_symbol} {yf_interval} from Yahoo Finance")
            
            # Fetch data
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(
                start=start_date,
                end=end_date,
                interval=yf_interval
            )
            
            if df.empty:
                logger.warning(f"No data returned for {yf_symbol}")
                return pd.DataFrame()
            
            # Rename columns to match our standard
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Keep only OHLCV columns
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # Reset index to have datetime as column
            df.reset_index(inplace=True)
            df.rename(columns={'Date': 'datetime'}, inplace=True)
            
            # Ensure datetime is timezone-naive
            if df['datetime'].dt.tz is not None:
                df['datetime'] = df['datetime'].dt.tz_localize(None)
            
            # Set datetime as index
            df.set_index('datetime', inplace=True)
            
            # Limit to requested number of candles
            if len(df) > limit:
                df = df.tail(limit)
            
            # Handle 4h timeframe (resample from 1h)
            if timeframe == '4h' and yf_interval == '1h':
                df = self._resample_to_4h(df)
            
            logger.info(f"Fetched {len(df)} candles for {yf_symbol} {yf_interval}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {symbol} from Yahoo Finance: {e}")
            raise
    
    def get_available_symbols(self) -> List[str]:
        """
        Get list of available symbols.
        Note: Yahoo Finance doesn't provide a direct API for this.
        Returns common forex pairs and indices.
        """
        common_symbols = [
            # Forex
            'EURUSD=X', 'GBPUSD=X', 'USDJPY=X', 'AUDUSD=X', 'USDCAD=X',
            'GBPJPY=X', 'EURJPY=X', 'EURGBP=X',
            # Metals
            'GC=F',  # Gold
            'SI=F',  # Silver
            'HG=F',  # Copper
            # Indices
            '^GSPC',  # S&P 500
            '^DJI',   # Dow Jones
            '^IXIC',  # NASDAQ
            '^FTSE',  # FTSE 100
            '^GDAXI', # DAX
        ]
        
        logger.info(f"Returning {len(common_symbols)} common symbols")
        return common_symbols
    
    def is_available(self) -> bool:
        """Check if Yahoo Finance is available."""
        try:
            # Try to fetch a simple ticker
            ticker = yf.Ticker('AAPL')
            info = ticker.info
            return 'symbol' in info
        except Exception as e:
            logger.warning(f"Yahoo Finance not available: {e}")
            return False
    
    def _convert_symbol(self, symbol: str) -> str:
        """
        Convert our symbol format to Yahoo Finance format.
        
        Examples:
            EURUSD -> EURUSD=X
            XAUUSD -> GC=F (Gold futures)
            XAGUSD -> SI=F (Silver futures)
            NAS100 -> ^IXIC
        """
        # Forex pairs (add =X suffix)
        if len(symbol) == 6 and symbol.isupper() and symbol.isalpha():
            return f"{symbol}=X"
        
        # Metals
        if symbol == 'XAUUSD':
            return 'GC=F'  # Gold futures
        if symbol == 'XAGUSD':
            return 'SI=F'  # Silver futures
        
        # Indices
        if symbol == 'NAS100':
            return '^IXIC'  # NASDAQ
        if symbol == 'US30':
            return '^DJI'   # Dow Jones
        if symbol == 'SPX500':
            return '^GSPC'  # S&P 500
        
        # Default: return as-is
        return symbol
    
    def _calculate_period(self, timeframe: str, limit: int) -> int:
        """Calculate number of days needed to get 'limit' candles."""
        # Rough estimates
        periods = {
            '1m': limit / (60 * 24),      # Minutes in a day
            '5m': limit / (12 * 24),      # 5-min candles in a day
            '15m': limit / (4 * 24),      # 15-min candles in a day
            '30m': limit / (2 * 24),      # 30-min candles in a day
            '1h': limit / 24,             # Hours in a day
            '4h': limit / 6,              # 4-hour candles in a day
            '1d': limit,                  # Days
            '1w': limit * 7,              # Weeks to days
            '1M': limit * 30              # Months to days
        }
        
        days = int(periods.get(timeframe, limit) * 1.5)  # Add 50% buffer
        return max(days, 7)  # Minimum 7 days
    
    def _resample_to_4h(self, df: pd.DataFrame) -> pd.DataFrame:
        """Resample 1h data to 4h."""
        df_4h = df.resample('4H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        # Drop rows with NaN (incomplete 4h periods)
        df_4h.dropna(inplace=True)
        
        return df_4h
