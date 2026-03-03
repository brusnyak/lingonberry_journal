#!/usr/bin/env python3
"""
Fetch real EURUSD data from cTrader - Simple working version
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
from ctrader_open_api.messages.OpenApiMessages_pb2 import *
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import *
from twisted.internet import reactor

# Credentials
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")

# Global state
client = None
account_id = None
trendbars_data = []

def onError(failure):
    """Error callback"""
    print(f"   ❌ Error: {failure}")
    reactor.stop()

def onTrendbarsReceived(message):
    """Handle trendbar response"""
    global trendbars_data
    
    # Extract the actual message
    msg = Protobuf.extract(message)
    print(f"   ✅ Received {len(msg.trendbar)} trendbars")
    trendbars_data = list(msg.trendbar)
    
    # Save to CSV
    save_to_csv(trendbars_data)
    
    # Stop reactor
    reactor.stop()

def save_to_csv(trendbars):
    """Save trendbars to CSV"""
    candles = []
    for bar in trendbars:
        candles.append({
            'time': datetime.fromtimestamp(bar.utcTimestampInMinutes * 60, tz=timezone.utc),
            'open': bar.open / 100000.0,  # cTrader uses 100000 multiplier
            'high': bar.high / 100000.0,
            'low': bar.low / 100000.0,
            'close': bar.close / 100000.0,
            'volume': bar.volume if hasattr(bar, 'volume') else 0
        })
    
    df = pd.DataFrame(candles)
    
    output_dir = Path("data/market_data")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = output_dir / "EURUSD_5m_real.csv"
    df.to_csv(csv_path, index=False)
    
    print(f"\n💾 Saved {len(candles)} candles to: {csv_path}")
    print(f"   Date range: {df['time'].min()} to {df['time'].max()}")
    print(f"   Price range: {df['low'].min():.5f} to {df['high'].max():.5f}")
    
    # Show first few rows
    print(f"\n   First 3 candles:")
    print(df.head(3).to_string())

def onAccountAuth(message):
    """Handle account auth response"""
    global client, account_id
    print(f"   ✅ Account {account_id} authenticated")
    
    # Fetch trendbars for EURUSD
    print("   📊 Fetching EURUSD 5-minute data...")
    
    # Get yesterday's data
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)
    
    print(f"      From: {start_time}")
    print(f"      To: {end_time}")
    
    request = ProtoOAGetTrendbarsReq()
    request.ctidTraderAccountId = account_id
    request.symbolId = 1  # EURUSD (may vary by broker)
    request.period = ProtoOATrendbarPeriod.M5
    request.fromTimestamp = int(start_time.timestamp() * 1000)
    request.toTimestamp = int(end_time.timestamp() * 1000)
    
    deferred = client.send(request)
    deferred.addCallbacks(onTrendbarsReceived, onError)

def onAccountList(message):
    """Handle account list response"""
    global client, account_id
    
    # Extract the actual message
    msg = Protobuf.extract(message)
    print(f"   Account list response: {msg}")
    
    if hasattr(msg, 'ctidTraderAccount') and msg.ctidTraderAccount:
        account_id = msg.ctidTraderAccount[0].ctidTraderAccountId
        print(f"   ✅ Found account: {account_id}")
        
        # Authorize account
        request = ProtoOAAccountAuthReq()
        request.ctidTraderAccountId = account_id
        request.accessToken = ACCESS_TOKEN
        
        deferred = client.send(request)
        deferred.addCallbacks(onAccountAuth, onError)
    else:
        print("   ❌ No accounts found")
        reactor.stop()

def onAppAuth(message):
    """Handle app auth response"""
    global client
    print("   ✅ Application authenticated")
    
    # Get account list
    request = ProtoOAGetAccountListByAccessTokenReq()
    request.accessToken = ACCESS_TOKEN
    
    deferred = client.send(request)
    deferred.addCallbacks(onAccountList, onError)

def connected(cli):
    """Connection callback"""
    global client
    client = cli
    print("   ✅ Connected to cTrader")
    
    # Authenticate application
    request = ProtoOAApplicationAuthReq()
    request.clientId = CLIENT_ID
    request.clientSecret = CLIENT_SECRET
    
    deferred = client.send(request)
    deferred.addCallbacks(onAppAuth, onError)

def disconnected(cli, reason):
    """Disconnection callback"""
    print(f"\n   Disconnected: {reason}")

def main():
    """Main function"""
    print("\n" + "="*70)
    print("📊 Fetch Real EURUSD Data from cTrader")
    print("="*70)
    
    # Check credentials
    if not all([CLIENT_ID, CLIENT_SECRET, ACCESS_TOKEN]):
        print("\n❌ Missing cTrader credentials in .env file")
        return False
    
    print(f"\n✅ Credentials loaded")
    print(f"   Client ID: {CLIENT_ID[:20]}...")
    
    print(f"\n🔌 Connecting to cTrader Demo API...")
    
    # Create client
    global client
    client = Client(EndPoints.PROTOBUF_DEMO_HOST, EndPoints.PROTOBUF_PORT, TcpProtocol)
    
    # Set callbacks
    client.setConnectedCallback(connected)
    client.setDisconnectedCallback(disconnected)
    
    # Start service
    client.startService()
    
    # Run reactor
    reactor.run()
    
    print("\n" + "="*70)
    print("✅ Complete!")
    print("="*70)
    
    return len(trendbars_data) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
