#!/usr/bin/env python3
"""
cTrader Open API Client
Handles communication with cTrader REST API
Documentation: https://openapi.ctrader.com/
"""
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# cTrader API configuration
CTRADER_API_URL = "https://openapi.ctrader.com"
CTRADER_CLIENT_ID = os.getenv("CTRADER_CLIENT_ID")
CTRADER_CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
CTRADER_ACCESS_TOKEN = os.getenv("CTRADER_ACCESS_TOKEN")
CTRADER_REFRESH_TOKEN = os.getenv("CTRADER_REFRESH_TOKEN")
CTRADER_ACCOUNT_ID = os.getenv("CTRADER_ACCOUNT_ID")


class CTraderClient:
    """cTrader Open API REST client"""
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        account_id: Optional[str] = None,
    ):
        self.client_id = client_id or CTRADER_CLIENT_ID
        self.client_secret = client_secret or CTRADER_CLIENT_SECRET
        self.access_token = access_token or CTRADER_ACCESS_TOKEN
        self.refresh_token = refresh_token or CTRADER_REFRESH_TOKEN
        self.account_id = account_id or CTRADER_ACCOUNT_ID
        self.api_url = CTRADER_API_URL
        self.connected = False
        self.session = requests.Session()
    
    def connect(self) -> bool:
        """Validate credentials and test connection"""
        if not all([self.client_id, self.client_secret, self.access_token]):
            print("❌ Missing cTrader credentials (CLIENT_ID, CLIENT_SECRET, ACCESS_TOKEN)")
            return False
        
        # Test connection by fetching accounts
        try:
            accounts = self.get_accounts()
            if accounts:
                self.connected = True
                print(f"✅ Connected to cTrader API - Found {len(accounts)} account(s)")
                return True
            else:
                print("⚠️ Connected but no accounts found")
                return False
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """Close session"""
        self.session.close()
        self.connected = False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make API request with error handling"""
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers()
        
        try:
            response = self.session.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print("⚠️ Access token expired, attempting refresh...")
                if self.refresh_access_token():
                    # Retry request with new token
                    headers = self._get_headers()
                    response = self.session.request(method, url, headers=headers, **kwargs)
                    response.raise_for_status()
                    return response.json() if response.content else {}
            raise
    
    def refresh_access_token(self) -> bool:
        """Refresh access token using refresh token"""
        if not self.refresh_token:
            print("❌ No refresh token available")
            return False
        
        try:
            response = requests.post(
                f"{self.api_url}/oauth/token",
                auth=HTTPBasicAuth(self.client_id, self.client_secret),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
            )
            response.raise_for_status()
            data = response.json()
            
            self.access_token = data["access_token"]
            if "refresh_token" in data:
                self.refresh_token = data["refresh_token"]
            
            print("✅ Access token refreshed")
            print(f"⚠️ Update your .env file with new tokens:")
            print(f"CTRADER_ACCESS_TOKEN={self.access_token}")
            if "refresh_token" in data:
                print(f"CTRADER_REFRESH_TOKEN={self.refresh_token}")
            
            return True
        except Exception as e:
            print(f"❌ Token refresh failed: {e}")
            return False
    
    def get_accounts(self) -> List[Dict]:
        """Get all trading accounts"""
        data = self._request("GET", "/v1/accounts")
        return data.get("data", [])
    
    def get_account_info(self, account_id: Optional[str] = None) -> Optional[Dict]:
        """Get specific account information"""
        acc_id = account_id or self.account_id
        if not acc_id:
            print("❌ No account ID provided")
            return None
        
        data = self._request("GET", f"/v2/accounts/{acc_id}")
        return data.get("data")
    
    def get_open_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        """Get open positions for account"""
        acc_id = account_id or self.account_id
        if not acc_id:
            return []
        
        data = self._request("GET", f"/v2/accounts/{acc_id}/positions")
        return data.get("data", [])
    
    def get_closed_positions(
        self,
        account_id: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Get closed positions (historical deals)"""
        acc_id = account_id or self.account_id
        if not acc_id:
            return []
        
        params = {"limit": limit}
        
        if from_ts:
            params["from"] = int(from_ts.timestamp() * 1000)
        if to_ts:
            params["to"] = int(to_ts.timestamp() * 1000)
        
        data = self._request("GET", f"/v2/accounts/{acc_id}/deals", params=params)
        return data.get("data", [])
    
    def get_historical_trades(
        self,
        account_id: Optional[str] = None,
        from_timestamp: Optional[int] = None,
        to_timestamp: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Get historical trades (alias for closed positions)"""
        acc_id = account_id or self.account_id
        
        from_ts = datetime.fromtimestamp(from_timestamp / 1000, tz=timezone.utc) if from_timestamp else None
        to_ts = datetime.fromtimestamp(to_timestamp / 1000, tz=timezone.utc) if to_timestamp else None
        
        return self.get_closed_positions(acc_id, from_ts, to_ts, limit)
    
    def get_symbols(self, account_id: Optional[str] = None) -> List[Dict]:
        """Get available trading symbols"""
        acc_id = account_id or self.account_id
        if not acc_id:
            return []
        
        data = self._request("GET", f"/v2/accounts/{acc_id}/symbols")
        return data.get("data", [])
    
    def get_trendbars(
        self,
        symbol: str,
        timeframe: str = "H1",
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        count: int = 1000,
        account_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get historical candlestick data (trendbars)
        
        Timeframes: M1, M5, M15, M30, H1, H4, D1, W1, MN1
        """
        acc_id = account_id or self.account_id
        if not acc_id:
            return []
        
        params = {
            "symbolName": symbol,
            "period": timeframe,
            "count": count,
        }
        
        if from_ts:
            params["from"] = int(from_ts.timestamp() * 1000)
        if to_ts:
            params["to"] = int(to_ts.timestamp() * 1000)
        
        data = self._request("GET", f"/v2/accounts/{acc_id}/trendbars", params=params)
        return data.get("data", [])


def create_client() -> CTraderClient:
    """Create and connect cTrader client"""
    client = CTraderClient()
    client.connect()
    return client


def test_connection():
    """Test cTrader API connection"""
    print("🔌 Testing cTrader API connection...\n")
    
    client = CTraderClient()
    
    if not client.connect():
        print("\n❌ Connection test failed")
        return False
    
    print("\n📊 Fetching account info...")
    accounts = client.get_accounts()
    for acc in accounts:
        print(f"  Account: {acc.get('login')} - {acc.get('brokerName')}")
        print(f"  Balance: {acc.get('balance')} {acc.get('currency')}")
        print(f"  Account ID: {acc.get('ctidTraderAccountId')}")
    
    if client.account_id:
        print(f"\n📈 Fetching open positions for account {client.account_id}...")
        positions = client.get_open_positions()
        print(f"  Found {len(positions)} open position(s)")
        
        print(f"\n📜 Fetching recent closed trades...")
        trades = client.get_closed_positions(limit=10)
        print(f"  Found {len(trades)} recent trade(s)")
        
        if trades:
            print("\n  Latest trade:")
            trade = trades[0]
            print(f"    Symbol: {trade.get('symbolName')}")
            print(f"    Volume: {trade.get('volume')}")
            print(f"    Entry: {trade.get('entryPrice')}")
            print(f"    Close: {trade.get('closePrice')}")
            print(f"    P&L: {trade.get('grossProfit')}")
    
    client.disconnect()
    print("\n✅ Connection test completed")
    return True


if __name__ == "__main__":
    test_connection()
