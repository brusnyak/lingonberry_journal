"""
Binance data source using CCXT.
"""
import ccxt
import pandas as pd
from typing import Optional, List
from datetime import datetime
from src.data.base import DataSource
from src.utils.logger import setup_logger
from src.config import BINANCE_API_KEY, BINANCE_SECRET_KEY

logger = setup_logger(__name__)


class BinanceSource(DataSource):
    """Binance data source for crypto markets."""
    
    def __init__(self, api_key: str = "", secret_key: str = ""):
        """
        Initialize Binance source.
        
        Args:
            api_key: Binance API key (optional for public data)
            secret_key: Binance secret key (optional for public data)
        """
        self.api_key = api_key or BINANCE_API_KEY
        self.secret_key = secret_key or BINANCE_SECRET_KEY
        
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.secret_key,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        logger.info("Binance source initialized")
    
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Binance.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Number of candles (max 1000)
            since: Start datetime
        
        Returns:
            DataFrame with columns: datetime, open, high, low, close, volume
        """
        try:
            # Convert datetime to timestamp if provided
            since_ms = None
            if since:
                since_ms = int(since.timestamp() * 1000)
            
            logger.debug(f"Fetching {symbol} {timeframe} from Binance (limit={limit})")
            
            # Fetch OHLCV
            ohlcv = self.exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=limit,
                since=since_ms
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # Convert timestamp to datetime
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Reorder columns
            df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
            
            # Set datetime as index
            df.set_index('datetime', inplace=True)
            
            logger.info(f"Fetched {len(df)} candles for {symbol} {timeframe}")
            
            return df
            
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching {symbol}: {e}")
            raise ConnectionError(f"Failed to connect to Binance: {e}")
        
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching {symbol}: {e}")
            raise ValueError(f"Invalid symbol or parameters: {e}")
        
        except Exception as e:
            logger.error(f"Unexpected error fetching {symbol}: {e}")
            raise
    
    def get_available_symbols(self) -> List[str]:
        """Get list of available trading pairs on Binance."""
        try:
            markets = self.exchange.load_markets()
            # Filter for USDT pairs (most liquid)
            symbols = [s for s in markets.keys() if '/USDT' in s]
            logger.info(f"Found {len(symbols)} USDT pairs on Binance")
            return sorted(symbols)
        
        except Exception as e:
            logger.error(f"Error loading markets: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if Binance API is available."""
        try:
            self.exchange.fetch_status()
            return True
        except Exception as e:
            logger.warning(f"Binance not available: {e}")
            return False
    
    def get_order_book(self, symbol: str, limit: int = 100) -> dict:
        """
        Fetch order book for order flow analysis.
        
        Args:
            symbol: Trading pair
            limit: Depth limit (5, 10, 20, 50, 100, 500, 1000)
        
        Returns:
            Dict with 'bids' and 'asks' arrays
        """
        try:
            order_book = self.exchange.fetch_order_book(symbol, limit=limit)
            logger.debug(f"Fetched order book for {symbol} (depth={limit})")
            return order_book
        
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}: {e}")
            raise
    
    def get_recent_trades(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """
        Fetch recent trades for order flow analysis.
        
        Args:
            symbol: Trading pair
            limit: Number of trades
        
        Returns:
            DataFrame with trade data
        """
        try:
            trades = self.exchange.fetch_trades(symbol, limit=limit)
            
            df = pd.DataFrame(trades)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Keep relevant columns
            df = df[['datetime', 'price', 'amount', 'side', 'id']]
            
            logger.debug(f"Fetched {len(df)} recent trades for {symbol}")
            
            return df
        
        except Exception as e:
            logger.error(f"Error fetching trades for {symbol}: {e}")
            raise
