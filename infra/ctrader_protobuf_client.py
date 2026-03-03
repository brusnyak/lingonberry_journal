#!/usr/bin/env python3
"""
cTrader Open API client (Protobuf/TCP) for historical and live data.

Auth + data flow follows official Spotware Open API docs:
1) ProtoOAApplicationAuthReq
2) ProtoOAGetAccountListByAccessTokenReq
3) ProtoOAAccountAuthReq
4) Symbols/trendbars/spot subscriptions
"""
import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

SDK_IMPORT_ERROR = None
CTRADER_AVAILABLE = False

try:
    from ctrader_open_api import Client, EndPoints, Protobuf, TcpProtocol
    from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent
    from ctrader_open_api.messages.OpenApiMessages_pb2 import (
        ProtoOAAccountAuthReq,
        ProtoOAApplicationAuthReq,
        ProtoOAErrorRes,
        ProtoOAGetAccountListByAccessTokenReq,
        ProtoOAGetAccountListByAccessTokenRes,
        ProtoOAGetTrendbarsReq,
        ProtoOAGetTrendbarsRes,
        ProtoOASpotEvent,
        ProtoOASymbolsListReq,
        ProtoOASubscribeSpotsReq,
        ProtoOAUnsubscribeSpotsReq,
    )
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
    from twisted.internet import reactor

    CTRADER_AVAILABLE = True
except Exception as exc_openapipy:
    try:
        from OpenApiPy import Client, EndPoints, Protobuf, TcpProtocol
        from OpenApiPy.messages.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent
        from OpenApiPy.messages.OpenApiMessages_pb2 import (
            ProtoOAAccountAuthReq,
            ProtoOAApplicationAuthReq,
            ProtoOAErrorRes,
            ProtoOAGetAccountListByAccessTokenReq,
            ProtoOAGetAccountListByAccessTokenRes,
            ProtoOAGetTrendbarsReq,
            ProtoOAGetTrendbarsRes,
            ProtoOASpotEvent,
            ProtoOASymbolsListReq,
            ProtoOASubscribeSpotsReq,
            ProtoOAUnsubscribeSpotsReq,
        )
        from OpenApiPy.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
        from twisted.internet import reactor

        CTRADER_AVAILABLE = True
    except Exception as exc_openapi:
        try:
            from OpenAPI.client import Client, EndPoints, Protobuf, TcpProtocol
            from OpenAPI.messages.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent
            from OpenAPI.messages.OpenApiMessages_pb2 import (
                ProtoOAAccountAuthReq,
                ProtoOAApplicationAuthReq,
                ProtoOAErrorRes,
                ProtoOAGetAccountListByAccessTokenReq,
                ProtoOAGetAccountListByAccessTokenRes,
                ProtoOAGetTrendbarsReq,
                ProtoOAGetTrendbarsRes,
                ProtoOASpotEvent,
                ProtoOASymbolsListReq,
                ProtoOASubscribeSpotsReq,
                ProtoOAUnsubscribeSpotsReq,
            )
            from OpenAPI.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
            from twisted.internet import reactor

            CTRADER_AVAILABLE = True
        except Exception as exc_legacy:
            SDK_IMPORT_ERROR = f"{exc_openapipy}; {exc_openapi}; {exc_legacy}"


class CTraderProtobufClient:
    """Blocking helper around cTrader OpenAPI deferred calls."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        account_id: Optional[str] = None,
        host_type: str = "demo",
    ):
        self.client_id = client_id or os.getenv("CTRADER_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("CTRADER_CLIENT_SECRET")
        self.access_token = access_token or os.getenv("CTRADER_ACCESS_TOKEN")
        self.account_id = int(account_id or os.getenv("CTRADER_ACCOUNT_ID") or 0) or None
        self.host_type = (host_type or os.getenv("CTRADER_HOST_TYPE", "demo")).lower()

        self.client = None
        self.connected = False
        self.accounts: List[Dict] = []
        self.symbols_by_name: Dict[str, Dict] = {}
        self.symbols_by_id: Dict[int, Dict] = {}
        self._connected_event = threading.Event()
        self._disconnected_event = threading.Event()
        self._quote_events: Dict[int, threading.Event] = {}
        self._latest_quotes: Dict[int, Dict] = {}

    def _ensure_sdk(self) -> bool:
        if CTRADER_AVAILABLE:
            return True
        print("❌ cTrader OpenAPI SDK is not installed.")
        print("   Install with: pip install ctrader-open-api twisted pyOpenSSL service_identity")
        if SDK_IMPORT_ERROR:
            print(f"   Import errors: {SDK_IMPORT_ERROR}")
        return False

    def _ensure_reactor_running(self) -> bool:
        if reactor.running:
            return True

        thread = threading.Thread(
            target=reactor.run,
            kwargs={"installSignalHandlers": False},
            daemon=True,
        )
        thread.start()

        deadline = time.time() + 3
        while not reactor.running and time.time() < deadline:
            time.sleep(0.05)
        return reactor.running

    def _send_request(self, request, timeout_seconds: int = 15):
        if not self.client:
            raise RuntimeError("Client is not connected")

        done = threading.Event()
        box: Dict[str, object] = {}

        def _ok(resp):
            try:
                parsed = Protobuf.extract(resp) if hasattr(resp, "payloadType") else resp
            except Exception:
                parsed = resp
            box["result"] = parsed
            done.set()
            return resp

        def _err(failure):
            message = failure.getErrorMessage() if hasattr(failure, "getErrorMessage") else str(failure)
            box["error"] = RuntimeError(message)
            done.set()
            return failure

        def _dispatch():
            try:
                deferred = self.client.send(request)
                deferred.addCallbacks(_ok, _err)
            except Exception as exc:
                box["error"] = exc
                done.set()

        reactor.callFromThread(_dispatch)

        if not done.wait(timeout_seconds):
            raise TimeoutError(f"Timed out waiting for {request.__class__.__name__} response")
        if "error" in box:
            raise box["error"]

        response = box.get("result")
        if response and hasattr(response, "errorCode") and hasattr(response, "description"):
            raise RuntimeError(f"cTrader error {response.errorCode}: {response.description}")
        return response

    def _on_connected(self, _client):
        self._connected_event.set()

    def _on_disconnected(self, _client, _reason):
        self.connected = False
        self._disconnected_event.set()

    def _scale_price(self, value: Optional[int], symbol_id: Optional[int] = None) -> Optional[float]:
        if value is None:
            return None
        digits = 5
        if symbol_id and symbol_id in self.symbols_by_id:
            digits = int(self.symbols_by_id[symbol_id].get("digits", 5))
        scale = 10 ** digits
        return round(float(value) / scale, digits)

    def _on_message_received(self, _client, message):
        try:
            if message.payloadType == ProtoHeartbeatEvent().payloadType:
                return

            if message.payloadType == ProtoOASpotEvent().payloadType:
                spot = Protobuf.extract(message)
                symbol_id = int(getattr(spot, "symbolId", 0))
                quote = {
                    "symbolId": symbol_id,
                    "bid": self._scale_price(getattr(spot, "bid", None), symbol_id),
                    "ask": self._scale_price(getattr(spot, "ask", None), symbol_id),
                    "timestamp": int(getattr(spot, "timestamp", int(time.time() * 1000))),
                }
                self._latest_quotes[symbol_id] = quote
                event = self._quote_events.get(symbol_id)
                if event:
                    event.set()
                return

            if message.payloadType == ProtoOAErrorRes().payloadType:
                error = Protobuf.extract(message)
                print(f"❌ API error: {getattr(error, 'errorCode', '?')} - {getattr(error, 'description', '')}")
        except Exception:
            return

    def connect(self, timeout_seconds: int = 20) -> bool:
        if not self._ensure_sdk():
            return False
        if not all([self.client_id, self.client_secret, self.access_token]):
            print("❌ Missing cTrader credentials (CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET, CTRADER_ACCESS_TOKEN)")
            return False
        if self.connected:
            return True
        if not self._ensure_reactor_running():
            print("❌ Failed to start Twisted reactor")
            return False

        self._connected_event.clear()
        self._disconnected_event.clear()

        host = EndPoints.PROTOBUF_LIVE_HOST if self.host_type == "live" else EndPoints.PROTOBUF_DEMO_HOST
        port = getattr(EndPoints, "PROTOBUF_PORT", 5035)

        def _create_and_start():
            self.client = Client(host, port, TcpProtocol)
            self.client.setConnectedCallback(self._on_connected)
            self.client.setDisconnectedCallback(self._on_disconnected)
            self.client.setMessageReceivedCallback(self._on_message_received)
            if hasattr(self.client, "startService"):
                self.client.startService()

        reactor.callFromThread(_create_and_start)

        if not self._connected_event.wait(timeout_seconds):
            print("❌ cTrader connection timeout")
            return False

        try:
            app_auth_req = ProtoOAApplicationAuthReq()
            app_auth_req.clientId = self.client_id
            app_auth_req.clientSecret = self.client_secret
            self._send_request(app_auth_req, timeout_seconds)

            account_req = ProtoOAGetAccountListByAccessTokenReq()
            account_req.accessToken = self.access_token
            account_res = self._send_request(account_req, timeout_seconds)

            self.accounts = []
            for account in getattr(account_res, "ctidTraderAccount", []):
                self.accounts.append(
                    {
                        "ctidTraderAccountId": int(getattr(account, "ctidTraderAccountId", 0)),
                        "brokerName": getattr(account, "brokerName", ""),
                        "accountType": getattr(account, "accountType", ""),
                        "isLive": bool(getattr(account, "isLive", False)),
                    }
                )

            if not self.accounts:
                print("❌ No trading accounts returned for this access token")
                return False

            if not self.account_id:
                self.account_id = int(self.accounts[0]["ctidTraderAccountId"])

            account_auth_req = ProtoOAAccountAuthReq()
            account_auth_req.ctidTraderAccountId = int(self.account_id)
            account_auth_req.accessToken = self.access_token
            self._send_request(account_auth_req, timeout_seconds)

            self.connected = True
            print(f"✅ Connected to cTrader {self.host_type.upper()} Open API (account {self.account_id})")
            return True
        except Exception as exc:
            print(f"❌ cTrader auth failed: {exc}")
            return False

    def disconnect(self):
        if not self.client:
            return

        def _stop():
            try:
                if hasattr(self.client, "stopService"):
                    self.client.stopService()
            except Exception:
                pass

        reactor.callFromThread(_stop)
        self.connected = False

    def get_accounts(self) -> List[Dict]:
        if not self.connected and not self.connect():
            return []
        return list(self.accounts)

    def get_symbols(self, account_id: Optional[str] = None) -> List[Dict]:
        if not self.connected and not self.connect():
            return []

        req = ProtoOASymbolsListReq()
        req.ctidTraderAccountId = int(account_id or self.account_id)

        try:
            res = self._send_request(req)
        except Exception as exc:
            print(f"❌ Failed to fetch symbols: {exc}")
            return []

        symbols: List[Dict] = []
        self.symbols_by_name.clear()
        self.symbols_by_id.clear()
        for symbol in getattr(res, "symbol", []):
            row = {
                "symbolId": int(getattr(symbol, "symbolId", 0)),
                "name": getattr(symbol, "symbolName", ""),
                "symbolName": getattr(symbol, "symbolName", ""),
                "digits": int(getattr(symbol, "digits", 5)),
            }
            symbols.append(row)
            if row["name"]:
                self.symbols_by_name[row["name"]] = row
                self.symbols_by_id[row["symbolId"]] = row

        return symbols

    def _resolve_symbol_id(self, symbol: str, account_id: Optional[str] = None) -> Optional[int]:
        if symbol and symbol.isdigit():
            return int(symbol)
        if symbol in self.symbols_by_name:
            return int(self.symbols_by_name[symbol]["symbolId"])
        self.get_symbols(account_id=account_id)
        if symbol in self.symbols_by_name:
            return int(self.symbols_by_name[symbol]["symbolId"])
        return None

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

        symbol_id = self._resolve_symbol_id(symbol, account_id=account_id)
        if not symbol_id:
            print(f"❌ Symbol not found: {symbol}")
            return []

        tf = timeframe.upper()
        if tf == "D":
            tf = "D1"
        period = getattr(ProtoOATrendbarPeriod, tf, None)
        if period is None:
            print(f"❌ Unsupported timeframe: {timeframe}")
            return []

        req = ProtoOAGetTrendbarsReq()
        req.ctidTraderAccountId = int(account_id or self.account_id)
        req.symbolId = int(symbol_id)
        req.period = period
        req.count = min(max(int(count), 1), 10000)

        if from_ts:
            req.fromTimestamp = int(from_ts.timestamp() * 1000)
        if to_ts:
            req.toTimestamp = int(to_ts.timestamp() * 1000)

        try:
            res = self._send_request(req)
        except Exception as exc:
            print(f"❌ Failed to fetch trendbars: {exc}")
            return []

        digits = int(self.symbols_by_id.get(int(symbol_id), {}).get("digits", 5))
        scale = float(10 ** digits)
        out: List[Dict] = []
        for bar in getattr(res, "trendbar", []):
            low_raw = float(getattr(bar, "low", 0))
            open_raw = low_raw + float(getattr(bar, "deltaOpen", 0))
            high_raw = low_raw + float(getattr(bar, "deltaHigh", 0))
            close_raw = low_raw + float(getattr(bar, "deltaClose", 0))
            minutes = int(getattr(bar, "utcTimestampInMinutes", 0))
            ts_ms = minutes * 60 * 1000

            out.append(
                {
                    "timestamp": ts_ms,
                    "datetime": datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc),
                    "open": round(open_raw / scale, digits),
                    "high": round(high_raw / scale, digits),
                    "low": round(low_raw / scale, digits),
                    "close": round(close_raw / scale, digits),
                    "volume": float(getattr(bar, "volume", 0)),
                }
            )

        return out

    def get_live_quote(self, symbol: str, timeout_seconds: int = 10, account_id: Optional[str] = None) -> Optional[Dict]:
        if not self.connected and not self.connect():
            return None

        symbol_id = self._resolve_symbol_id(symbol, account_id=account_id)
        if not symbol_id:
            print(f"❌ Symbol not found: {symbol}")
            return None

        event = threading.Event()
        self._quote_events[int(symbol_id)] = event

        req = ProtoOASubscribeSpotsReq()
        req.ctidTraderAccountId = int(account_id or self.account_id)
        req.symbolId.append(int(symbol_id))

        try:
            self._send_request(req, timeout_seconds=timeout_seconds)
            event.wait(timeout_seconds)
            quote = self._latest_quotes.get(int(symbol_id))
            return quote
        except Exception as exc:
            print(f"❌ Failed to fetch live quote: {exc}")
            return None
        finally:
            self._quote_events.pop(int(symbol_id), None)
            try:
                unsub = ProtoOAUnsubscribeSpotsReq()
                unsub.ctidTraderAccountId = int(account_id or self.account_id)
                unsub.symbolId.append(int(symbol_id))
                self._send_request(unsub, timeout_seconds=3)
            except Exception:
                pass
