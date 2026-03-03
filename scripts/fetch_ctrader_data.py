#!/usr/bin/env python3
"""
Fetch real EURUSD data from cTrader Open API
Uses official ctrader-open-api library
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Import cTrader Open API
from ctrader_open_api import Client, Protobuf, TcpProtocol, Auth
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import *
from ctrader_open_api.messages.OpenApiMessages_pb2 import *
from twisted.internet import reactor

sys.path.insert(0, str(Path(__file__).parent.parent))

# cTrader credentials
CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
ACCOUNT_ID = os.getenv("CTRADER_ACCOUNT_ID")

# cTrader API endpoints
HOST = "demo.ctraderapi.com"  # Demo server
PORT = 5035  # TCP port

class CTraderDataFetcher:
    """Fetch market data from cTrader"""
    
    def __init__(self):
        self.client = None
        self.account_id = None
        self.data = []
        
    def on_message(self, message):
        """Handle incoming messages"""
        if message.payloadType == ProtoOAPayloadType.PROTO_OA_GET_TRENDBARS_RES:
            print(f"   Received {len(message.trendbar)} trendbars")
            self.data = message.trendbar
            reactor.stop()
        elif message.payloadType == ProtoOAPayloadType.PROTO_OA_ERROR_RES:
            print(f"   ❌ Error: {message.errorCode} - {message.description}")
            reactor.stop()
    
    def on_connect(self):
        """Called when connected"""
        print("   ✅ Connected to cTrader")
        
        # Authenticate application
        request = ProtoOAApplicationAuthReq()
        request.clientId = CLIENT_ID
        request.clientSecret = CLIENT_SECRET
        
        self.client.send(request)
        
    def on_app_auth(self, message):
        """Called after app authentication"""
        print("   ✅ Application authenticated")
        
        # Get account list
        request = ProtoOAGetAccountListByAccessTokenReq()
        request.accessToken = ACCESS_TOKEN
        
        self.client.send(request)
    
    def on_account_list(self, message):
        """Called after receiving account list"""
        if message.ctidTraderAccount:
            self.account_id = message.ctidTraderAccount[0].ctidTraderAccountId
            print(f"   ✅ Found account: {self.account_id}")
            
            # Authorize account
            request = ProtoOAAccountAuthReq()
            request.ctidTraderAccountId = self.account_id
            request.accessToken = ACCESS_TOKEN
            
            self.client.send(request)
        else:
            print("   ❌ No accounts found")
            reactor.stop()
    
    def on_account_auth(self, message):
        """Called after account authentication"""
        print("   ✅ Account authenticated")
        
        # Now fetch trendbars
        self.fetch_trendbars()
    
    def fetch_trendbars(self):
        """Fetch EURUSD trendbars"""
        print("   📊 Fetching EURUSD 5-minute data...")
        
        # Get yesterday's data
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)
        
        request = ProtoOAGetTrendbarsReq()
        request.ctidTraderAccountId = self.account_id
        request.symbolId = 1  # EURUSD symbol ID (may vary by broker)
        request.period = ProtoOATrendbarPeriod.M5
        request.fromTimestamp = int(start_time.timestamp() * 1000)
        request.toTimestamp = int(end_time.timestamp() * 1000)
        
        self.client.send(request)
    
    def start(self):
        """Start the client"""
        print("\n🔌 Connecting to cTrader API...")
        
        # Create client
        self.client = Client(HOST, PORT, TcpProtocol)
        
        # Set up message handlers
        self.client.setMessageHandler(ProtoOAPayloadType.PROTO_OA_APPLICATION_AUTH_RES, self.on_app_auth)
        self.client.setMessageHandler(ProtoOAPayloadType.PROTO_OA_GET_ACCOUNT_LIST_BY_ACCESS_TOKEN_RES, self.on_account_list)
        self.client.setMessageHandler(ProtoOAPayloadType.PROTO_OA_ACCOUNT_AUTH_RES, self.on_account_auth)
        self.client.setMessageHandler(ProtoOAPayloadType.PROTO_OA_GET_TRENDBARS_RES, self.on_message)
        self.client.setMessageHandler(ProtoOAPayloadType.PROTO_OA_ERROR_RES, self.on_message)
        
        # Set connect callback
        self.client.setConnectedCallback(self.on_connect)
        
        # Start connection
        self.client.startService()
        
        # Run reactor
        reactor.run()
        
        return self.data

def main():
    """Main function"""
    print("\n" + "="*70)
    print("📊 cTrader Data Fetcher")
    print("="*70)
    
    # Check credentials
    if not all([CLIENT_ID, CLIENT_SECRET, ACCESS_TOKEN, ACCOUNT_ID]):
        print("\n❌ Missing cTrader credentials in .env file")
        print("   Required: CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET,")
        print("             CTRADER_ACCESS_TOKEN, CTRADER_ACCOUNT_ID")
        return False
    
    print(f"\n✅ Credentials loaded")
    print(f"   Client ID: {CLIENT_ID[:20]}...")
    print(f"   Account ID: {ACCOUNT_ID}")
    
    # Fetch data
    fetcher = CTraderDataFetcher()
    data = fetcher.start()
    
    if data:
        print(f"\n✅ Fetched {len(data)} candles")
        print(f"\n   First candle:")
        first = data[0]
        print(f"      Time: {datetime.fromtimestamp(first.timestamp/1000, tz=timezone.utc)}")
        print(f"      Open: {first.open}")
        print(f"      High: {first.high}")
        print(f"      Low: {first.low}")
        print(f"      Close: {first.close}")
        
        # Save to CSV
        import pandas as pd
        
        candles = []
        for bar in data:
            candles.append({
                'time': datetime.fromtimestamp(bar.timestamp/1000, tz=timezone.utc),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume if hasattr(bar, 'volume') else 0
            })
        
        df = pd.DataFrame(candles)
        
        output_dir = Path("data/market_data")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = output_dir / "EURUSD_5m_ctrader.csv"
        df.to_csv(csv_path, index=False)
        
        print(f"\n💾 Saved to: {csv_path}")
        print("\n" + "="*70)
        print("✅ Complete!")
        print("="*70)
        
        return True
    else:
        print("\n❌ No data received")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
