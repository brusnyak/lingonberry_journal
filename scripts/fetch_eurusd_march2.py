#!/usr/bin/env python3
"""
Fetch EURUSD data from cTrader for March 2, 2026
Clean implementation using ctrader-open-api library
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# Import cTrader Open API
try:
    from ctrader_open_api import Client, Protobuf, TcpProtocol
    from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
    from ctrader_open_api.messages.OpenApiMessages_pb2 import *
    from twisted.internet import reactor
except ImportError as e:
    print(f"❌ Missing required library: {e}")
    print("   Install with: pip install ctrader-open-api twisted")
    sys.exit(1)

# cTrader credentials from .env
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
ACCOUNT_ID = os.getenv("CTRADER_ACCOUNT_ID")

# cTrader API endpoints (use demo or live)
HOST = "demo.ctraderapi.com"  # Change to "live.ctraderapi.com" for live
PORT = 5035

# Output directory
OUTPUT_DIR = Path("data/market_data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class CTraderFetcher:
    """Fetch market data from cTrader Open API"""
    
    def __init__(self, target_date=None):
        self.client = None
        self.account_id = None
        self.symbol_id = None
        self.trendbars = []
        self.target_date = target_date or datetime.now(timezone.utc).date()
        self.error = None
        
    def on_message(self, client, message):
        """Handle all incoming messages"""
        # Extract payload from ProtoMessage wrapper
        from ctrader_open_api import Protobuf
        
        payload = Protobuf.extract(message)
        msg_type = type(payload).__name__
        
        print(f"📨 Received: {msg_type}")
        
        if msg_type == 'ProtoOAApplicationAuthRes':
            self.on_app_auth(payload)
        elif msg_type == 'ProtoOAGetAccountListByAccessTokenRes':
            self.on_account_list(payload)
        elif msg_type == 'ProtoOAAccountAuthRes':
            self.on_account_auth(payload)
        elif msg_type == 'ProtoOASymbolsListRes':
            self.on_symbols_list(payload)
        elif msg_type == 'ProtoOAGetTrendbarsRes':
            self.on_trendbars(payload)
        elif msg_type == 'ProtoOAErrorRes':
            self.on_error(payload)
        else:
            print(f"⚠️  Unhandled message type: {msg_type}")
    
    def on_connect(self, client):
        """Called when connected to cTrader"""
        print("✅ Connected to cTrader API")
        print("🔐 Authenticating application...")
        
        # Step 1: Authenticate application
        request = ProtoOAApplicationAuthReq()
        request.clientId = CLIENT_ID
        request.clientSecret = CLIENT_SECRET
        client.send(request)
    
    def on_app_auth(self, message):
        """Called after app authentication"""
        print("✅ Application authenticated")
        print("📋 Fetching account list...")
        
        # Step 2: Get account list
        request = ProtoOAGetAccountListByAccessTokenReq()
        request.accessToken = ACCESS_TOKEN
        self.client.send(request)
    
    def on_account_list(self, message):
        """Called after receiving account list"""
        if not message.ctidTraderAccount:
            print("❌ No accounts found")
            self.error = "No accounts found"
            reactor.stop()
            return
        
        # Use first account or match ACCOUNT_ID from env
        for acc in message.ctidTraderAccount:
            if ACCOUNT_ID and str(acc.ctidTraderAccountId) == ACCOUNT_ID:
                self.account_id = acc.ctidTraderAccountId
                break
        
        if not self.account_id:
            self.account_id = message.ctidTraderAccount[0].ctidTraderAccountId
        
        print(f"✅ Using account: {self.account_id}")
        print("🔐 Authenticating account...")
        
        # Step 3: Authorize account
        request = ProtoOAAccountAuthReq()
        request.ctidTraderAccountId = self.account_id
        request.accessToken = ACCESS_TOKEN
        self.client.send(request)
    
    def on_account_auth(self, message):
        """Called after account authentication"""
        print("✅ Account authenticated")
        print("📊 Fetching symbol list...")
        
        # Step 4: Get symbols to find EURUSD symbol ID
        request = ProtoOASymbolsListReq()
        request.ctidTraderAccountId = self.account_id
        self.client.send(request)
    
    def on_symbols_list(self, message):
        """Called after receiving symbols list"""
        # Find EURUSD symbol
        for symbol in message.symbol:
            if symbol.symbolName == "EURUSD":
                self.symbol_id = symbol.symbolId
                print(f"✅ Found EURUSD symbol ID: {self.symbol_id}")
                break
        
        if not self.symbol_id:
            print("❌ EURUSD symbol not found")
            self.error = "EURUSD symbol not found"
            reactor.stop()
            return
        
        # Step 5: Fetch trendbars
        self.fetch_trendbars()
    
    def fetch_trendbars(self):
        """Fetch EURUSD 5-minute trendbars for target date"""
        # Set time range for target date (full day)
        start_time = datetime.combine(self.target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_time = datetime.combine(self.target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        print(f"📈 Fetching EURUSD 5-minute data for {self.target_date}...")
        print(f"   From: {start_time}")
        print(f"   To: {end_time}")
        
        request = ProtoOAGetTrendbarsReq()
        request.ctidTraderAccountId = self.account_id
        request.symbolId = self.symbol_id
        request.period = ProtoOATrendbarPeriod.M5  # 5-minute candles
        request.fromTimestamp = int(start_time.timestamp() * 1000)
        request.toTimestamp = int(end_time.timestamp() * 1000)
        
        self.client.send(request)
    
    def on_trendbars(self, message):
        """Called when trendbars are received"""
        print(f"✅ Received {len(message.trendbar)} trendbars")
        
        if not message.trendbar:
            print("⚠️  No data available for this date")
            self.error = "No data available"
            reactor.stop()
            return
        
        # Convert trendbars to readable format
        for bar in message.trendbar:
            # cTrader uses relative pricing - convert to actual prices
            low = bar.low / 100000.0
            high = (bar.low + bar.deltaHigh) / 100000.0
            open_price = (bar.low + bar.deltaOpen) / 100000.0
            close = (bar.low + bar.deltaClose) / 100000.0
            
            self.trendbars.append({
                'time': datetime.fromtimestamp(bar.timestamp / 1000, tz=timezone.utc),
                'open': round(open_price, 5),
                'high': round(high, 5),
                'low': round(low, 5),
                'close': round(close, 5),
                'volume': bar.volume if hasattr(bar, 'volume') else 0
            })
        
        print(f"✅ Processed {len(self.trendbars)} candles")
        reactor.stop()
    
    def on_error(self, message):
        """Called when error is received"""
        error_code = message.errorCode if hasattr(message, 'errorCode') else 'Unknown'
        description = message.description if hasattr(message, 'description') else 'No description'
        print(f"❌ cTrader API Error: {error_code} - {description}")
        self.error = f"{error_code}: {description}"
        reactor.stop()
    
    def start(self):
        """Start the fetcher"""
        print("\n" + "="*70)
        print("📊 cTrader EURUSD Data Fetcher")
        print("="*70)
        
        # Validate credentials
        if not all([CLIENT_ID, CLIENT_SECRET, ACCESS_TOKEN]):
            print("\n❌ Missing cTrader credentials in .env file")
            print("   Required: CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET, CTRADER_ACCESS_TOKEN")
            return None
        
        print(f"\n✅ Credentials loaded")
        print(f"   Client ID: {CLIENT_ID[:20]}...")
        if ACCOUNT_ID:
            print(f"   Account ID: {ACCOUNT_ID}")
        
        print(f"\n🔌 Connecting to {HOST}:{PORT}...")
        
        # Create client
        self.client = Client(HOST, PORT, TcpProtocol)
        
        # Set message received callback
        self.client.setMessageReceivedCallback(self.on_message)
        
        # Set connect callback
        self.client.setConnectedCallback(self.on_connect)
        
        # Start connection
        self.client.startService()
        
        # Run reactor (blocking until stopped)
        reactor.run()
        
        return self.trendbars


def main():
    """Main function"""
    # Target date: March 2, 2026
    target_date = datetime(2026, 3, 2).date()
    
    # Create fetcher
    fetcher = CTraderFetcher(target_date=target_date)
    
    # Fetch data
    data = fetcher.start()
    
    if not data:
        print("\n❌ Failed to fetch data")
        if fetcher.error:
            print(f"   Error: {fetcher.error}")
        return False
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Save to CSV
    csv_path = OUTPUT_DIR / f"EURUSD_5m_{target_date.strftime('%Y%m%d')}.csv"
    df.to_csv(csv_path, index=False)
    
    print(f"\n💾 Saved to: {csv_path}")
    print(f"\n📊 Data Summary:")
    print(f"   Total candles: {len(df)}")
    print(f"   Date range: {df['time'].min()} to {df['time'].max()}")
    print(f"   Price range: {df['low'].min():.5f} - {df['high'].max():.5f}")
    
    print(f"\n📈 First 5 candles:")
    print(df.head().to_string(index=False))
    
    print("\n" + "="*70)
    print("✅ Complete!")
    print("="*70)
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
