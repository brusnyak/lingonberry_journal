#!/usr/bin/env python3
"""
Test cTrader Integration
Fetches trades and market data, saves to CSV/Parquet
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from infra.ctrader_client import CTraderClient

# Output directories
OUTPUT_DIR = Path("data/exports")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def test_connection():
    """Test basic connection"""
    print("=" * 60)
    print("TEST 1: Connection Test")
    print("=" * 60)
    
    client = CTraderClient()
    success = client.connect()
    
    if success:
        print("\n✅ Connection successful!")
        accounts = client.get_accounts()
        print(f"\nFound {len(accounts)} account(s):")
        for acc in accounts:
            print(f"  - {acc.get('login')} ({acc.get('brokerName')})")
            print(f"    Balance: {acc.get('balance')} {acc.get('currency')}")
            print(f"    ID: {acc.get('ctidTraderAccountId')}")
    else:
        print("\n❌ Connection failed!")
        return False
    
    client.disconnect()
    return True


def test_fetch_trades():
    """Fetch historical trades and save to CSV/Parquet"""
    print("\n" + "=" * 60)
    print("TEST 2: Fetch Historical Trades")
    print("=" * 60)
    
    client = CTraderClient()
    if not client.connect():
        print("❌ Connection failed")
        return False
    
    try:
        # Fetch last 30 days of trades
        to_ts = datetime.now(timezone.utc)
        from_ts = to_ts - timedelta(days=30)
        
        print(f"\nFetching trades from {from_ts.date()} to {to_ts.date()}...")
        trades = client.get_closed_positions(from_ts=from_ts, to_ts=to_ts, limit=100)
        
        print(f"✅ Found {len(trades)} trade(s)")
        
        if not trades:
            print("⚠️ No trades found in the last 30 days")
            return True
        
        # Convert to DataFrame
        df = pd.DataFrame(trades)
        
        # Add calculated fields
        df['direction'] = df['tradeSide'].apply(lambda x: 'LONG' if x == 'BUY' else 'SHORT')
        df['pnl'] = df['grossProfit'] + df.get('commission', 0) + df.get('swap', 0)
        df['open_time'] = pd.to_datetime(df['openTimestamp'], unit='ms')
        df['close_time'] = pd.to_datetime(df['closeTimestamp'], unit='ms')
        df['duration_minutes'] = (df['closeTimestamp'] - df['openTimestamp']) / 1000 / 60
        
        # Select relevant columns
        export_cols = [
            'dealId', 'symbolName', 'direction', 'volume',
            'entryPrice', 'closePrice', 'pnl', 'grossProfit',
            'commission', 'swap', 'open_time', 'close_time', 'duration_minutes'
        ]
        df_export = df[export_cols]
        
        # Save to CSV
        csv_path = OUTPUT_DIR / f"ctrader_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_export.to_csv(csv_path, index=False)
        print(f"\n✅ Saved to CSV: {csv_path}")
        
        # Save to Parquet
        parquet_path = OUTPUT_DIR / f"ctrader_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        df_export.to_parquet(parquet_path, index=False)
        print(f"✅ Saved to Parquet: {parquet_path}")
        
        # Print summary
        print("\n📊 Trade Summary:")
        print(f"  Total Trades: {len(df)}")
        print(f"  Total P&L: {df['pnl'].sum():.2f}")
        print(f"  Winning Trades: {len(df[df['pnl'] > 0])}")
        print(f"  Losing Trades: {len(df[df['pnl'] < 0])}")
        print(f"  Win Rate: {len(df[df['pnl'] > 0]) / len(df) * 100:.1f}%")
        
        print("\n📈 Top 5 Trades:")
        print(df_export.nlargest(5, 'pnl')[['symbolName', 'direction', 'pnl', 'open_time']])
        
        return True
        
    finally:
        client.disconnect()


def test_fetch_market_data():
    """Fetch market data (trendbars) and save to CSV/Parquet"""
    print("\n" + "=" * 60)
    print("TEST 3: Fetch Market Data (Trendbars)")
    print("=" * 60)
    
    client = CTraderClient()
    if not client.connect():
        print("❌ Connection failed")
        return False
    
    try:
        # Test with GBPJPY on multiple timeframes
        symbol = "GBPJPY"
        timeframes = ["5m", "30m", "4h"]
        
        to_ts = datetime.now(timezone.utc)
        from_ts = to_ts - timedelta(days=7)  # Last 7 days
        
        for tf in timeframes:
            print(f"\nFetching {symbol} {tf} data...")
            
            # Map timeframe to cTrader format
            tf_map = {"5m": "M5", "30m": "M30", "4h": "H4", "1h": "H1", "1d": "D1"}
            ct_tf = tf_map.get(tf, "H1")
            
            trendbars = client.get_trendbars(
                symbol=symbol,
                timeframe=ct_tf,
                from_ts=from_ts,
                to_ts=to_ts,
                count=1000
            )
            
            if not trendbars:
                print(f"  ⚠️ No data found for {symbol} {tf}")
                continue
            
            print(f"  ✅ Found {len(trendbars)} candles")
            
            # Convert to DataFrame
            df = pd.DataFrame(trendbars)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Rename columns to standard OHLCV format
            df = df.rename(columns={
                'timestamp': 'time',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })
            
            # Select relevant columns
            df_export = df[['time', 'open', 'high', 'low', 'close', 'volume']]
            
            # Save to CSV
            csv_path = OUTPUT_DIR / f"ctrader_{symbol}_{tf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df_export.to_csv(csv_path, index=False)
            print(f"  ✅ Saved to CSV: {csv_path}")
            
            # Save to Parquet
            parquet_path = OUTPUT_DIR / f"ctrader_{symbol}_{tf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
            df_export.to_parquet(parquet_path, index=False)
            print(f"  ✅ Saved to Parquet: {parquet_path}")
            
            # Print sample
            print(f"\n  Sample data (first 3 rows):")
            print(df_export.head(3).to_string(index=False))
        
        return True
        
    finally:
        client.disconnect()


def main():
    """Run all tests"""
    print("\n🚀 cTrader Integration Test Suite\n")
    
    # Test 1: Connection
    if not test_connection():
        print("\n❌ Connection test failed. Please check your credentials in .env")
        return
    
    # Test 2: Fetch trades
    if not test_fetch_trades():
        print("\n❌ Trade fetch test failed")
        return
    
    # Test 3: Fetch market data
    if not test_fetch_market_data():
        print("\n❌ Market data fetch test failed")
        return
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    print(f"\nExported files are in: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
