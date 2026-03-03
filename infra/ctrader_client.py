#!/usr/bin/env python3
"""
High-level cTrader client.

Uses cTrader Open API Protobuf for market/account data and /apps/token for token refresh.
"""
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

try:
    from infra.ctrader_protobuf_client import CTRADER_AVAILABLE, CTraderProtobufClient
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from infra.ctrader_protobuf_client import CTRADER_AVAILABLE, CTraderProtobufClient

load_dotenv()

CTRADER_OAUTH_URL = "https://openapi.ctrader.com/apps/token"


class CTraderClient:
    """Facade used by the rest of the project."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        account_id: Optional[str] = None,
        host_type: Optional[str] = None,
    ):
        self.client_id = client_id or os.getenv("CTRADER_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("CTRADER_CLIENT_SECRET")
        self.access_token = access_token or os.getenv("CTRADER_ACCESS_TOKEN")
        self.refresh_token = refresh_token or os.getenv("CTRADER_REFRESH_TOKEN")
        self.account_id = account_id or os.getenv("CTRADER_ACCOUNT_ID")
        self.host_type = (host_type or os.getenv("CTRADER_HOST_TYPE", "demo")).lower()

        self.connected = False
        self._protobuf: Optional[CTraderProtobufClient] = None

    def _build_protobuf_client(self) -> CTraderProtobufClient:
        return CTraderProtobufClient(
            client_id=self.client_id,
            client_secret=self.client_secret,
            access_token=self.access_token,
            account_id=self.account_id,
            host_type=self.host_type,
        )

    def connect(self) -> bool:
        if not CTRADER_AVAILABLE:
            # Protobuf SDK is required for account/data operations.
            self._protobuf = self._build_protobuf_client()
            self._protobuf._ensure_sdk()
            return False
        if not all([self.client_id, self.client_secret]):
            print("❌ Missing cTrader credentials (CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET)")
            return False
        if not self.access_token:
            if not self.refresh_access_token():
                print("❌ Missing/invalid access token and refresh failed")
                return False

        self._protobuf = self._build_protobuf_client()
        if self._protobuf.connect():
            self.connected = True
            self.account_id = str(self._protobuf.account_id) if self._protobuf.account_id else self.account_id
            return True

        # One retry after refresh in case token expired.
        if self.refresh_token and self.refresh_access_token():
            self._protobuf = self._build_protobuf_client()
            if self._protobuf.connect():
                self.connected = True
                self.account_id = str(self._protobuf.account_id) if self._protobuf.account_id else self.account_id
                return True

        self.connected = False
        return False

    def disconnect(self) -> None:
        if self._protobuf:
            self._protobuf.disconnect()
        self.connected = False

    def refresh_access_token(self) -> bool:
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            return False

        auth = HTTPBasicAuth(self.client_id, self.client_secret)
        params = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}

        try:
            # Official docs show query params; many clients also accept form body.
            response = requests.get(CTRADER_OAUTH_URL, auth=auth, params=params, timeout=15)
            if response.status_code >= 400:
                response = requests.post(CTRADER_OAUTH_URL, auth=auth, data=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            print(f"❌ Token refresh failed: {exc}")
            return False

        self.access_token = payload.get("accessToken") or payload.get("access_token")
        self.refresh_token = payload.get("refreshToken") or payload.get("refresh_token") or self.refresh_token
        if not self.access_token:
            print(f"❌ Token refresh response did not include access token: {payload}")
            return False

        self._update_env_tokens(self.access_token, self.refresh_token)
        print("✅ Refreshed cTrader access token")
        return True

    def _update_env_tokens(self, access_token: str, refresh_token: str) -> None:
        env_path = ".env"
        if not os.path.exists(env_path):
            return

        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        found_access = False
        found_refresh = False
        output: List[str] = []
        for line in lines:
            if line.startswith("CTRADER_ACCESS_TOKEN="):
                output.append(f"CTRADER_ACCESS_TOKEN={access_token}\n")
                found_access = True
            elif line.startswith("CTRADER_REFRESH_TOKEN="):
                output.append(f"CTRADER_REFRESH_TOKEN={refresh_token}\n")
                found_refresh = True
            else:
                output.append(line)

        if not found_access:
            output.append(f"CTRADER_ACCESS_TOKEN={access_token}\n")
        if not found_refresh:
            output.append(f"CTRADER_REFRESH_TOKEN={refresh_token}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(output)

    def get_accounts(self) -> List[Dict]:
        if not self.connected and not self.connect():
            return []
        return self._protobuf.get_accounts() if self._protobuf else []

    def get_account_info(self, account_id: Optional[str] = None) -> Optional[Dict]:
        accounts = self.get_accounts()
        target_id = int(account_id or self.account_id or 0)
        for account in accounts:
            if int(account.get("ctidTraderAccountId", 0)) == target_id:
                return account
        return accounts[0] if accounts else None

    def get_symbols(self, account_id: Optional[str] = None) -> List[Dict]:
        if not self.connected and not self.connect():
            return []
        return self._protobuf.get_symbols(account_id=account_id) if self._protobuf else []

    def get_trendbars(
        self,
        symbol: str,
        timeframe: str = "H1",
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        count: int = 1000,
        account_id: Optional[str] = None,
    ) -> List[Dict]:
        if not self.connected and not self.connect():
            return []
        return (
            self._protobuf.get_trendbars(
                symbol=symbol,
                timeframe=timeframe,
                from_ts=from_ts,
                to_ts=to_ts,
                count=count,
                account_id=account_id,
            )
            if self._protobuf
            else []
        )

    def get_live_quote(self, symbol: str, account_id: Optional[str] = None) -> Optional[Dict]:
        if not self.connected and not self.connect():
            return None
        return self._protobuf.get_live_quote(symbol=symbol, account_id=account_id) if self._protobuf else None

    def get_open_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        # Trading/positions endpoints can be added here later via additional ProtoOA messages.
        _ = account_id
        return []

    def get_closed_positions(
        self,
        account_id: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict]:
        # Historical deal import is not wired yet in this adapter.
        _ = (account_id, from_ts, to_ts, limit)
        return []

    def get_historical_trades(
        self,
        account_id: Optional[str] = None,
        from_timestamp: Optional[int] = None,
        to_timestamp: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict]:
        from_ts = datetime.fromtimestamp(from_timestamp / 1000, tz=timezone.utc) if from_timestamp else None
        to_ts = datetime.fromtimestamp(to_timestamp / 1000, tz=timezone.utc) if to_timestamp else None
        return self.get_closed_positions(account_id=account_id, from_ts=from_ts, to_ts=to_ts, limit=limit)


def create_client() -> CTraderClient:
    client = CTraderClient()
    client.connect()
    return client


def test_connection() -> bool:
    print("🔌 Testing cTrader Open API connection...\n")
    client = CTraderClient()
    if not client.connect():
        print("❌ Connection failed")
        return False

    try:
        accounts = client.get_accounts()
        print(f"✅ Connected. Accounts available: {len(accounts)}")
        if accounts:
            first = accounts[0]
            print(f"   Account ID: {first.get('ctidTraderAccountId')}")
            print(f"   Broker: {first.get('brokerName')}")

        symbols = client.get_symbols()
        print(f"✅ Symbols loaded: {len(symbols)}")

        quote = client.get_live_quote("EURUSD")
        if quote:
            print(f"✅ EURUSD live quote bid/ask: {quote.get('bid')} / {quote.get('ask')}")
        else:
            print("⚠️ Live quote not received in time window")
        return True
    finally:
        client.disconnect()


if __name__ == "__main__":
    test_connection()
