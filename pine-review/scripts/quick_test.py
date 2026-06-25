#!/usr/bin/env python
"""Quick test of data fetching without full dependencies."""
import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("Testing data pipeline...")
print("="*60)

# Test 1: Load existing parquet file
print("\n1. Loading existing parquet file...")
data_path = Path(__file__).parent.parent.parent / 'data' / 'parquet' / 'crypto' / 'BTCUSD1440.parquet'

if data_path.exists():
    df = pd.read_parquet(data_path)
    print(f"✓ Loaded {len(df)} candles")
    
    # Check if datetime is column or index
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        last_date = df['datetime'].iloc[-1]
        first_date = df['datetime'].iloc[0]
    else:
        last_date = df.index[-1]
        first_date = df.index[0]
    
    print(f"  Date range: {first_date} to {last_date}")
    print(f"  Columns: {list(df.columns)}")
    print(f"\n  Last 3 candles:")
    print(df.tail(3))
    
    # Check gap
    from datetime import datetime
    now = datetime.now()
    
    # Ensure last_date is datetime
    if not isinstance(last_date, pd.Timestamp):
        last_date = pd.to_datetime(last_date)
    
    gap_days = (now - last_date).days
    print(f"\n  Gap: {gap_days} days (last update: {last_date.date()})")
else:
    print(f"✗ File not found: {data_path}")

# Test 2: Try Binance fetch
print("\n2. Testing Binance data fetch...")
try:
    from src.data import BinanceSource
    
    source = BinanceSource()
    df_new = source.fetch_ohlcv('BTC/USDT', '1d', limit=5)
    
    print(f"✓ Fetched {len(df_new)} candles from Binance")
    print(f"  Latest candle: {df_new.index[-1]}")
    print(df_new.tail(3))
    
except Exception as e:
    print(f"✗ Binance fetch failed: {e}")

print("\n" + "="*60)
print("Test complete!")
