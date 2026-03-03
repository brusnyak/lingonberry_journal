#!/usr/bin/env python3
"""
Test cTrader API Connection and Data Fetching
Validates credentials and fetches sample historical/live data
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.ctrader_client import CTraderClient


def test_authentication():
    """Test 1: Validate credentials and connection"""
    print("=" * 60)
    print("TEST 1: Authentication & Connection")
    print("=" * 60)
    
    client = CTraderClient()
    
    print(f"\n📋 Credentials loaded:")
    print(f"   Client ID: {client.client_id[:20]}..." if client.client_id else "   ❌ Missing")
    print(f"   Client Secret: {client.client_secret[:20]}..." if client.client_secret else "   ❌ Missing")
    print(f"   Access Token: {client.access_token[:20]}..." if client.access_token else "   ❌ Missing")
    print(f"   Refresh Token: {client.refresh_token[:20]}..." if client.refresh_token else "   ❌ Missing")
    
    if not client.connect():
        print("\n❌ Connection failed - check your credentials")
        return None
    
    print("\n✅ Authentication successful")
    return client


def test_accounts(client):
    """Test 2: Fetch trading accounts"""
    print("\n" + "=" * 60)
    print("TEST 2: Fetch Trading Accounts")
    print("=" * 60)
    
    accounts = client.get_accounts()
    
    if not accounts:
        print("❌ No accounts found")
        return None
    
    print(f"\n✅ Found {len(accounts)} account(s):\n")
    
    for i, acc in enumerate(accounts, 1):
        print(f"Account {i}:")
        print(f"   Login: {acc.get('login')}")
        print(f"   Broker: {acc.get('brokerName')}")
        print(f"   Balance: {acc.get('balance')} {acc.get('currency')}")
        print(f"   Account ID: {acc.get('ctidTraderAccountId')}")
        print(f"   Type: {acc.get('accountType')}")
        print()
    
    # Use first account for subsequent tests
    account_id = str(accounts[0].get('ctidTraderAccountId'))
    client.account_id = account_id
    
    return account_id


def test_symbols(client):
    """Test 3: Fetch available symbols"""
    print("=" * 60)
    print("TEST 3: Fetch Available Symbols")
    print("=" * 60)
    
    symbols = client.get_symbols()
    
    if not symbols:
        print("❌ No symbols found")
        return []
    
    print(f"\n✅ Found {len(symbols)} symbols")
    
    # Show major forex pairs
    major_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
    found_pairs = []
    
    print("\n📊 Major Forex Pairs:")
    for sym in symbols:
        name = sym.get("name")
        if name in major_pairs:
            found_pairs.append(name)
            print(f"   {name}: ID={sym.get('symbolId')}, Digits={sym.get('digits')}")
    
    return found_pairs


def test_historical_data(client, symbol="EURUSD"):
    """Test 4: Fetch historical candlestick data"""
    print("\n" + "=" * 60)
    print(f"TEST 4: Fetch Historical Data ({symbol})")
    print("=" * 60)
    
    # Fetch last 100 H1 candles
    to_ts = datetime.now(timezone.utc)
    from_ts = to_ts - timedelta(days=7)
    
    print(f"\n📅 Requesting data:")
    print(f"   Symbol: {symbol}")
    print(f"   Timeframe: H1")
    print(f"   From: {from_ts.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   To: {to_ts.strftime('%Y-%m-%d %H:%M UTC')}")
    
    trendbars = client.get_trendbars(
        symbol=symbol,
        timeframe="H1",
        from_ts=from_ts,
        to_ts=to_ts,
        count=100
    )
    
    if not trendbars:
        print(f"\n❌ No data received for {symbol}")
        return False
    
    print(f"\n✅ Received {len(trendbars)} candles")
    
    # Show first and last candles
    if len(trendbars) > 0:
        print("\n📊 First candle:")
        first = trendbars[0]
        print(f"   Time: {datetime.fromtimestamp(first.get('timestamp', 0)/1000, tz=timezone.utc)}")
        print(f"   Open: {first.get('open')}")
        print(f"   High: {first.get('high')}")
        print(f"   Low: {first.get('low')}")
        print(f"   Close: {first.get('close')}")
        print(f"   Volume: {first.get('volume')}")
        
        print("\n📊 Last candle:")
        last = trendbars[-1]
        print(f"   Time: {datetime.fromtimestamp(last.get('timestamp', 0)/1000, tz=timezone.utc)}")
        print(f"   Open: {last.get('open')}")
        print(f"   High: {last.get('high')}")
        print(f"   Low: {last.get('low')}")
        print(f"   Close: {last.get('close')}")
        print(f"   Volume: {last.get('volume')}")
    
    return True


def test_multiple_timeframes(client, symbol="EURUSD"):
    """Test 5: Fetch data across different timeframes"""
    print("\n" + "=" * 60)
    print(f"TEST 5: Multiple Timeframes ({symbol})")
    print("=" * 60)
    
    timeframes = ["M5", "M15", "H1", "H4", "D1"]
    to_ts = datetime.now(timezone.utc)
    
    print(f"\n📊 Testing timeframes:")
    
    for tf in timeframes:
        # Adjust lookback based on timeframe
        if tf.startswith("M"):
            days = 2
        elif tf == "H1":
            days = 7
        elif tf == "H4":
            days = 14
        else:  # D1
            days = 30
        
        from_ts = to_ts - timedelta(days=days)
        
        trendbars = client.get_trendbars(
            symbol=symbol,
            timeframe=tf,
            from_ts=from_ts,
            to_ts=to_ts,
            count=100
        )
        
        if trendbars:
            print(f"   ✅ {tf:4s}: {len(trendbars):3d} candles")
        else:
            print(f"   ❌ {tf:4s}: No data")


def test_live_quote(client, symbol="EURUSD"):
    """Test 6: Fetch live quote (if available via REST)"""
    print("\n" + "=" * 60)
    print(f"TEST 6: Live Quote ({symbol})")
    print("=" * 60)
    
    quote = client.get_live_quote(symbol)
    
    if quote:
        print(f"\n✅ Live quote received:")
        print(f"   Bid: {quote.get('bid')}")
        print(f"   Ask: {quote.get('ask')}")
        print(f"   Spread: {quote.get('spread')}")
        print(f"   Time: {datetime.fromtimestamp(quote.get('timestamp', 0)/1000, tz=timezone.utc)}")
    else:
        print("\n⚠️ Live quotes may require WebSocket connection")
        print("   (REST API primarily for historical data)")


def main():
    """Run all tests"""
    print("\n" + "🔬 cTrader API Connection Test Suite")
    print("=" * 60)
    
    # Test 1: Authentication
    client = test_authentication()
    if not client:
        return
    
    # Test 2: Accounts
    account_id = test_accounts(client)
    if not account_id:
        return
    
    # Test 3: Symbols
    symbols = test_symbols(client)
    
    # Test 4: Historical data
    test_symbol = symbols[0] if symbols else "EURUSD"
    test_historical_data(client, test_symbol)
    
    # Test 5: Multiple timeframes
    test_multiple_timeframes(client, test_symbol)
    
    # Test 6: Live quote
    test_live_quote(client, test_symbol)
    
    # Cleanup
    client.disconnect()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed")
    print("=" * 60)
    print("\n💡 Next steps:")
    print("   - Use client.get_trendbars() for historical data")
    print("   - Use WebSocket for real-time streaming")
    print("   - Check docs: https://help.ctrader.com/open-api/")


if __name__ == "__main__":
    main()
