"""
Tests for data pipeline.
"""
import pytest
from src.data import DataManager, BinanceSource, YFinanceSource, DataCache


def test_binance_source():
    """Test Binance data fetching."""
    source = BinanceSource()
    
    # Test availability
    assert source.is_available()
    
    # Test OHLCV fetch
    df = source.fetch_ohlcv('BTC/USDT', '1h', limit=10)
    
    assert not df.empty
    assert len(df) == 10
    assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
    assert df.index.name == 'datetime'
    
    print(f"✓ Binance: Fetched {len(df)} candles for BTC/USDT")
    print(df.head())


def test_yfinance_source():
    """Test Yahoo Finance data fetching."""
    source = YFinanceSource()
    
    # Test availability
    assert source.is_available()
    
    # Test OHLCV fetch (forex)
    df = source.fetch_ohlcv('EURUSD', '1d', limit=10)
    
    assert not df.empty
    assert len(df) <= 10  # May be less due to weekends
    assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
    
    print(f"✓ Yahoo Finance: Fetched {len(df)} candles for EURUSD")
    print(df.head())


def test_data_manager():
    """Test unified data manager."""
    manager = DataManager()
    
    # Register sources
    manager.register_source('binance', BinanceSource())
    manager.register_source('yfinance', YFinanceSource())
    
    # Test auto-detection
    df_crypto = manager.fetch_ohlcv('BTC/USDT', '1h', limit=5)
    assert not df_crypto.empty
    print(f"✓ Auto-detected Binance for BTC/USDT")
    
    df_forex = manager.fetch_ohlcv('EURUSD', '1d', limit=5)
    assert not df_forex.empty
    print(f"✓ Auto-detected Yahoo Finance for EURUSD")


def test_cache():
    """Test data caching."""
    cache = DataCache()
    
    # Clear cache first
    cache.clear_all()
    
    # Test cache miss
    df = cache.get('BTC/USDT', '1h', 'binance')
    assert df is None
    print("✓ Cache miss works")
    
    # Fetch and cache data
    source = BinanceSource()
    df_original = source.fetch_ohlcv('BTC/USDT', '1h', limit=5)
    cache.set('BTC/USDT', '1h', 'binance', df_original)
    
    # Test cache hit
    df_cached = cache.get('BTC/USDT', '1h', 'binance', max_age_minutes=5)
    assert df_cached is not None
    assert len(df_cached) == len(df_original)
    print("✓ Cache hit works")
    
    # Test cache expiry
    df_expired = cache.get('BTC/USDT', '1h', 'binance', max_age_minutes=0)
    assert df_expired is None
    print("✓ Cache expiry works")


if __name__ == '__main__':
    print("Testing Data Pipeline...\n")
    
    print("1. Testing Binance Source...")
    test_binance_source()
    
    print("\n2. Testing Yahoo Finance Source...")
    test_yfinance_source()
    
    print("\n3. Testing Data Manager...")
    test_data_manager()
    
    print("\n4. Testing Cache...")
    test_cache()
    
    print("\n✅ All tests passed!")
