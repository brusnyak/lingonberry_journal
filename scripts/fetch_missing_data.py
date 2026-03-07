#!/usr/bin/env python3
"""
Fetch missing market data for symbols in the UI
"""
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.market_data import load_ohlcv_with_cache

# Symbols that need data - all forex/commodities should work with cTrader
SYMBOLS = [
    ("USDJPY", "forex"),
    ("XAUUSD", "forex"),  # Try as forex since cTrader has it
    ("XAGUSD", "forex"),  # Try as forex since cTrader has it
    ("US100", "forex"),   # Try as forex since cTrader has it
]

TIMEFRAMES = ["M5", "M15", "M30", "H1", "H4"]

def fetch_all():
    """Fetch data for all missing symbols"""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=90)  # 3 months of data
    
    for symbol, asset_type in SYMBOLS:
        print(f"\n📊 Fetching {symbol} ({asset_type})...")
        for tf in TIMEFRAMES:
            print(f"  ⏱️  {tf}...", end=" ")
            try:
                df = load_ohlcv_with_cache(
                    symbol=symbol,
                    asset_type=asset_type,
                    timeframe=tf,
                    start=start,
                    end=end,
                    ttl_seconds=0  # Force fresh fetch
                )
                if not df.empty:
                    print(f"✅ {len(df)} candles")
                else:
                    print("⚠️  No data")
            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    fetch_all()
    print("\n✅ Done!")
