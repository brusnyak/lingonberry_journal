"""
cTrader Open API Client — synchronous wrapper around protobuf/Twisted.

Single TCP connection, multiple accounts authed. All methods take an optional
account_id parameter (defaults to the primary/first account).

Usage:
    # Single account (singleton for webapp)
    from infra.ctrader_client import get_ctrader
    ct = get_ctrader()
    ct.get_positions()

    # Multi-account (copy trader)
    ct = CtraderClient(account_ids=[44798689, 47747211])
    ct.connect()
    ct.get_positions(account_id=44798689)
    ct.create_order("BTCUSD", 0.01, "buy", account_id=47747211)
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CtraderError(RuntimeError):
    """Base error."""


class CtraderAuthError(CtraderError):
    """Auth failure."""


class CtraderConnectionError(CtraderError):
    """Connection failure."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CtraderPosition:
    position_id: int
    symbol: str
    side: str
    volume_cents: int       # raw from proto; divide by 100_000 for lots
    open_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    swap: float = 0.0
    commission: float = 0.0
    pnl: float = 0.0

    @property
    def lots(self) -> float:
        return self.volume_cents / 100_000


@dataclass
class CtraderOrderResult:
    order_id: int | None = None
    status: str = "error"
    message: str = ""


@dataclass
class CtraderSymbol:
    symbol_id: int
    symbol_name: str
    enabled: bool
    digits: int = 0           # price decimal places (e.g. 3 for BTCUSD)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


# Period enum → minutes lookup
_PERIOD_MINUTES = {1: 1, 2: 5, 3: 15, 4: 30, 5: 60, 6: 240, 7: 1440}


from infra.client_interface import ClientInterface


class CtraderClient(ClientInterface):
    """Synchronous cTrader protobuf client — single connection, multi-account."""

    def __init__(
        self,
        account_ids: list[int] | None = None,
        client_id: str | None = None,
        secret: str | None = None,
        access_token: str | None = None,
    ):
        self._client_id = client_id or os.getenv("CTRADER_CLIENT_ID", "")
        self._secret = secret or os.getenv("CTRADER_SECRET", "")
        self._access_token = access_token or os.getenv("CTRADER_ACCESS_TOKEN", "")

        if not all([self._client_id, self._secret, self._access_token]):
            raise CtraderAuthError(
                "Missing cTrader credentials. Set CTRADER_CLIENT_ID, "
                "CTRADER_SECRET, CTRADER_ACCESS_TOKEN in .env"
            )

        # Resolve account IDs
        if account_ids:
            self._account_ids = account_ids
        else:
            default = os.getenv("CTRADER_ACCOUNT_ID", "0")
            self._account_ids = [int(default)]

        if not self._account_ids or self._account_ids[0] == 0:
            raise CtraderAuthError(
                "No account IDs provided. Pass account_ids or set CTRADER_ACCOUNT_ID in .env"
            )

        self._primary_account = self._account_ids[0]

        # Twisted internals
        self._reactor = None
        self._proto: Any = None    # ctrader_open_api Client instance
        self._connected = False
        self._authed_accounts: set[int] = set()

        # Symbol cache per account: {account_id: {symbol_id: CtraderSymbol}}
        self._sym_by_id: dict[int, dict[int, CtraderSymbol]] = {}
        self._sym_by_name: dict[int, dict[str, CtraderSymbol]] = {}
        self._symbols_loaded: set[int] = set()

    @property
    def account_ids(self) -> list[int]:
        """Account IDs this client is connected to."""
        return list(self._account_ids)

    # ── Connection ────────────────────────────────────────────────────────

    def connect(self, timeout: float = 30.0):
        """Connect to cTrader demo server, auth app + all accounts, load symbols."""
        from twisted.internet import reactor as tw_reactor

        self._start_reactor(tw_reactor)
        self._create_proto(timeout)
        self._auth_app(timeout)
        for aid in self._account_ids:
            self._auth_account(aid, timeout)
        # Load symbols for all accounts
        for aid in self._account_ids:
            self._load_symbols(aid, timeout)
        self._connected = True

    def _start_reactor(self, reactor):
        """Ensure Twisted reactor runs in a background thread."""
        if reactor.running:
            self._reactor = reactor
            return
        self._reactor = reactor
        t = threading.Thread(target=reactor.run, args=(False,), daemon=True)
        t.start()
        for _ in range(100):
            if reactor.running:
                return
            time.sleep(0.05)
        raise CtraderConnectionError("Reactor did not start")

    def _create_proto(self, timeout: float):
        """Create Client and connect. Blocks until connected or timeout."""
        from ctrader_open_api import Client, EndPoints
        from ctrader_open_api.tcpProtocol import TcpProtocol

        connected = threading.Event()
        errors = []

        def on_connected(proto):
            connected.set()

        def on_disconnected(proto, reason):
            errors.append(str(reason))
            connected.set()

        proto = Client(
            host=EndPoints.PROTOBUF_DEMO_HOST,
            port=EndPoints.PROTOBUF_PORT,
            protocol=TcpProtocol,
        )
        proto.setConnectedCallback(on_connected)
        proto.setDisconnectedCallback(on_disconnected)

        def _start():
            proto.startService()

        self._reactor.callFromThread(_start)
        if not connected.wait(timeout=timeout):
            raise CtraderConnectionError("Connection timed out")
        if errors:
            raise CtraderConnectionError(f"Connection failed: {errors[0]}")

        self._proto = proto

    def _send(self, msg, response_timeout: float = 15.0) -> Any:
        """Send protobuf msg, block until response, return ProtoMessage envelope."""
        from twisted.internet import reactor
        from twisted.internet.threads import blockingCallFromThread
        from twisted.python.failure import Failure

        result: list[Any] = []
        error: list[Failure | None] = [None]
        event = threading.Event()

        def _do_send():
            d = self._proto.send(msg, responseTimeoutInSeconds=int(response_timeout))
            d.addCallbacks(
                lambda r: (result.append(r), event.set()) and r,
                lambda f: (error.__setitem__(0, f), event.set()) and f,
            )
            return d

        try:
            blockingCallFromThread(self._reactor, _do_send)
            event.wait()
        except Exception as exc:
            raise CtraderError(f"Send failed: {exc}") from exc

        if error[0] is not None:
            msg_str = str(error[0].value)
            if "Timeout" in msg_str:
                raise CtraderError(f"Response timed out after {response_timeout}s")
            raise CtraderError(f"cTrader error: {msg_str}")

        return result[0]

    def _extract(self, resp) -> Any:
        """Extract inner protobuf message from ProtoMessage envelope."""
        from ctrader_open_api import Protobuf
        return Protobuf.extract(resp)

    # ── Auth ──────────────────────────────────────────────────────────────

    def _auth_app(self, timeout: float):
        from ctrader_open_api import Protobuf
        req = Protobuf.get(
            "ProtoOAApplicationAuthReq",
            clientId=self._client_id,
            clientSecret=self._secret,
        )
        self._send(req, timeout)

    def _auth_account(self, account_id: int, timeout: float):
        from ctrader_open_api import Protobuf
        if account_id in self._authed_accounts:
            return
        req = Protobuf.get(
            "ProtoOAAccountAuthReq",
            ctidTraderAccountId=account_id,
            accessToken=self._access_token,
        )
        self._send(req, timeout)
        self._authed_accounts.add(account_id)

    def _ensure_auth(self, account_id: int, timeout: float = 15.0):
        """Auth a specific account if not already done."""
        if account_id not in self._authed_accounts:
            self._auth_account(account_id, timeout)

    # ── Symbol cache ──────────────────────────────────────────────────────

    def _load_symbols(self, account_id: int, timeout: float):
        from ctrader_open_api import Protobuf
        if account_id in self._symbols_loaded:
            return
        req = Protobuf.get(
            "ProtoOASymbolsListReq",
            ctidTraderAccountId=account_id,
        )
        resp = self._send(req, timeout)
        msg = self._extract(resp)

        by_id: dict[int, CtraderSymbol] = {}
        by_name: dict[str, CtraderSymbol] = {}
        for sym in getattr(msg, "symbol", []):
            name = getattr(sym, "symbolName", "")
            s = CtraderSymbol(
                symbol_id=sym.symbolId,
                symbol_name=name,
                enabled=getattr(sym, "enabled", False),
                digits=getattr(sym, "digits", 0),
            )
            by_id[s.symbol_id] = s
            if name:
                by_name[name.upper()] = s

        self._sym_by_id[account_id] = by_id
        self._sym_by_name[account_id] = by_name
        self._symbols_loaded.add(account_id)

    # ── Symbols ───────────────────────────────────────────────────────────

    def _get_sym_by_id(self, account_id: int | None = None) -> dict[int, CtraderSymbol]:
        aid = account_id or self._primary_account
        return self._sym_by_id.get(aid, {})

    def _get_sym_by_name(self, account_id: int | None = None) -> dict[str, CtraderSymbol]:
        aid = account_id or self._primary_account
        return self._sym_by_name.get(aid, {})

    def get_symbols(self, account_id: int | None = None) -> list[CtraderSymbol]:
        return list(self._get_sym_by_id(account_id).values())

    def get_symbol_id(self, name: str, account_id: int | None = None) -> int | None:
        s = self._get_sym_by_name(account_id).get(name.upper())
        return s.symbol_id if s else None

    def get_symbol_digits(self, name: str, account_id: int | None = None) -> int:
        """Return decimal digits for a symbol (e.g. 3 for BTCUSD). Defaults to 5."""
        s = self._get_sym_by_name(account_id).get(name.upper())
        return s.digits if s else 5

    def get_crypto_symbols(self, account_id: int | None = None) -> list[CtraderSymbol]:
        crypto = {"BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD", "DOTUSD",
                  "DOGEUSD", "LTCUSD", "NEARUSD", "ARBUSD", "UNIUSD", "XLMUSD",
                  "BNBUSD", "AVAXUSD", "SUIUSD"}
        by_id = self._get_sym_by_id(account_id)
        return [s for s in by_id.values()
                if s.symbol_name.upper() in crypto]

    # ── Positions ─────────────────────────────────────────────────────────

    def get_positions(self, account_id: int | None = None) -> list[CtraderPosition]:
        """Get all open positions for the given account (or primary)."""
        aid = account_id or self._primary_account
        self._ensure_auth(aid)
        from ctrader_open_api import Protobuf

        req = Protobuf.get("ProtoOAReconcileReq", ctidTraderAccountId=aid)
        resp = self._send(req)
        msg = self._extract(resp)

        by_id = self._get_sym_by_id(aid)
        result = []
        for p in getattr(msg, "position", []):
            td = getattr(p, "tradeData", None)
            if td is None:
                continue

            sym = by_id.get(getattr(td, "symbolId", 0))
            sym_name = sym.symbol_name if sym else "?"

            side_code = getattr(td, "tradeSide", 0)
            side = "buy" if side_code == 1 else "sell"

            sl = p.stopLoss if hasattr(p, "stopLoss") and p.stopLoss else None
            tp = p.takeProfit if hasattr(p, "takeProfit") and p.takeProfit else None

            result.append(CtraderPosition(
                position_id=p.positionId,
                symbol=sym_name,
                side=side,
                volume_cents=getattr(td, "volume", 0),
                open_price=float(getattr(p, "price", 0)),
                stop_loss=float(sl) if sl else None,
                take_profit=float(tp) if tp else None,
                swap=float(getattr(p, "swap", 0)) / 100,
                commission=float(getattr(p, "commission", 0)) / 100,
                pnl=0.0,
            ))
        return result

    # ── Account ───────────────────────────────────────────────────────────

    def get_account_info(self, account_id: int | None = None) -> dict[str, Any]:
        """Get balance, equity, margin for the given account (or primary)."""
        aid = account_id or self._primary_account
        self._ensure_auth(aid)
        from ctrader_open_api import Protobuf

        req = Protobuf.get("ProtoOATraderReq", ctidTraderAccountId=aid)
        resp = self._send(req)
        msg = self._extract(resp)
        trader = getattr(msg, "trader", None)

        if trader is None:
            return {"error": "No trader data"}

        balance_cents = getattr(trader, "balance", 0)
        money_digits = getattr(trader, "moneyDigits", 2)
        divisor = 10 ** money_digits

        return {
            "account_id": aid,
            "balance": balance_cents / divisor,
            "leverage": getattr(trader, "leverageInCents", 10000) / 100,
            "currency_id": getattr(trader, "depositAssetId", 0),
            "trader_login": getattr(trader, "traderLogin", 0),
            "broker": getattr(trader, "brokerName", ""),
        }

    # ── Orders ────────────────────────────────────────────────────────────

    def create_order(
        self,
        symbol: str,
        quantity: float,
        side: str,
        order_type: str = "market",
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        account_id: int | None = None,
        entry_price: float | None = None,
    ) -> CtraderOrderResult:
        """Place a market order on the given account (or primary).

        For MARKET orders, SL/TP must be relative distances in points.
        Pass ``entry_price`` = estimated fill price; the method converts
        absolute SL/TP to relative distances using the symbol's decimal digits.
        For LIMIT/STOP orders, absolute SL/TP values are used directly.
        """
        aid = account_id or self._primary_account
        self._ensure_auth(aid)
        from ctrader_open_api import Protobuf

        sym_id = self.get_symbol_id(symbol, account_id=aid)
        if sym_id is None:
            return CtraderOrderResult(message=f"Unknown symbol: {symbol} for account {aid}")

        trade_side = 1 if side.lower() == "buy" else 2
        type_code = 1  # MARKET
        if order_type == "limit":
            type_code = 2
        elif order_type == "stop":
            type_code = 3

        volume = int(quantity * 100_000)
        digits = self.get_symbol_digits(symbol, account_id=aid)
        scale = 10 ** digits

        params = {
            "ctidTraderAccountId": aid,
            "symbolId": sym_id,
            "orderType": type_code,
            "tradeSide": trade_side,
            "volume": volume,
        }
        if price is not None:
            params["limitPrice"] = price

        # MARKET orders require relative SL/TP (distance in points)
        if type_code == 1:
            if stop_loss is not None and entry_price is not None:
                if side.lower() == "buy":
                    rel_sl = int(round((entry_price - stop_loss) * scale))
                else:
                    rel_sl = int(round((stop_loss - entry_price) * scale))
                if rel_sl > 0:
                    params["relativeStopLoss"] = rel_sl
            if take_profit is not None and entry_price is not None:
                if side.lower() == "buy":
                    rel_tp = int(round((take_profit - entry_price) * scale))
                else:
                    rel_tp = int(round((entry_price - take_profit) * scale))
                if rel_tp > 0:
                    params["relativeTakeProfit"] = rel_tp
        else:
            # LIMIT/STOP orders use absolute SL/TP, rounded to symbol digits
            if stop_loss is not None:
                params["stopLoss"] = round(stop_loss, digits)
            if take_profit is not None:
                params["takeProfit"] = round(take_profit, digits)

        try:
            req = Protobuf.get("ProtoOANewOrderReq", **params)
            resp = self._send(req, response_timeout=20.0)
            msg = self._extract(resp)

            # Execution event → order accepted, position created
            pos = getattr(msg, "position", None)
            if pos is not None:
                pos_id = getattr(pos, "positionId", None)
                if pos_id:
                    return CtraderOrderResult(
                        order_id=pos_id,
                        status="filled",
                        message=f"Order filled: {side} {quantity} {symbol} on account {aid}",
                    )

            # Order error event
            error_code = getattr(msg, "errorCode", None)
            if error_code:
                desc = getattr(msg, "description", str(msg))
                return CtraderOrderResult(message=f"{error_code}: {desc}")

            # Fallback: look for orderId
            order_id = getattr(msg, "orderId", None)
            if order_id:
                return CtraderOrderResult(
                    order_id=order_id,
                    status="filled",
                    message=f"Order placed: {side} {quantity} {symbol} on account {aid}",
                )

            return CtraderOrderResult(message=f"No orderId in response: {msg}")
        except Exception as exc:
            return CtraderOrderResult(message=str(exc))

    def close_position(
        self,
        position_id: int,
        volume: int = 0,
        account_id: int | None = None,
    ) -> CtraderOrderResult:
        """Close a position by ID on the given account (or primary).

        Args:
            position_id: Position to close.
            volume: Volume in proto units (0 = auto, will fetch and use full volume).
            account_id: Account to close on (or primary).
        """
        aid = account_id or self._primary_account
        self._ensure_auth(aid)
        from ctrader_open_api import Protobuf

        if volume <= 0:
            # Fetch the position volume
            pos_list = self.get_positions(account_id=aid)
            for p in pos_list:
                if p.position_id == position_id:
                    volume = p.volume_cents
                    break
            if volume <= 0:
                return CtraderOrderResult(
                    message=f"Cannot close position {position_id}: volume unknown or zero"
                )

        req = Protobuf.get(
            "ProtoOAClosePositionReq",
            ctidTraderAccountId=aid,
            positionId=position_id,
            volume=volume,
        )
        try:
            resp = self._send(req, response_timeout=20.0)
            msg = self._extract(resp)

            # Execution event → close accepted
            pos = getattr(msg, "position", None)
            if pos is not None:
                pos_id = getattr(pos, "positionId", None)
                if pos_id:
                    return CtraderOrderResult(
                        order_id=pos_id,
                        status="closed",
                        message=f"Position {pos_id} closed on account {aid}",
                    )

            # Error event
            error_code = getattr(msg, "errorCode", None)
            if error_code:
                desc = getattr(msg, "description", str(msg))
                return CtraderOrderResult(message=f"{error_code}: {desc}")

            return CtraderOrderResult(message=f"Unexpected close response: {msg}")
        except Exception as exc:
            return CtraderOrderResult(message=str(exc))

    # ── OHLC data ─────────────────────────────────────────────────────────

    def get_ohlc(
        self,
        symbol: str,
        period: int = 2,
        count: int = 50,
        account_id: int | None = None,
    ) -> "pd.DataFrame | None":
        """Fetch OHLC bars via ProtoOAGetTrendbarsReq.

        Args:
            symbol: Symbol name (e.g. "BTCUSD", "EURUSD").
            period: 1=M1, 2=M5 (default), 3=M15, 4=M30, 5=H1, 6=H4, 7=D1.
            count: Number of bars to fetch (default 50, max 1000).
            account_id: Account to use (or primary).

        Returns:
            DataFrame with columns: open, high, low, close
            Index: datetime (UTC).  None on error.
        """
        import pandas as pd

        aid = account_id or self._primary_account
        self._ensure_auth(aid)

        sym_id = self.get_symbol_id(symbol.upper(), account_id=aid)
        if sym_id is None:
            return None

        import time as _time
        from ctrader_open_api import Protobuf

        now_ms = int(_time.time() * 1000)
        # Fetch more than needed to have enough after shift/lookback
        fetch_count = min(count + 20, 1000)
        # Go back far enough: count * period_minutes * 60 * 1000
        period_minutes = _PERIOD_MINUTES.get(period, 5)
        from_ms = now_ms - fetch_count * period_minutes * 60 * 1000

        req = Protobuf.get(
            "ProtoOAGetTrendbarsReq",
            ctidTraderAccountId=aid,
            symbolId=sym_id,
            period=period,
            fromTimestamp=from_ms,
            toTimestamp=now_ms,
            count=fetch_count,
        )
        resp = self._send(req)
        msg = self._extract(resp)

        bars = getattr(msg, "trendbar", [])
        if not bars:
            return None

        rows = []
        for b in bars:
            ts_min = getattr(b, "utcTimestampInMinutes", 0)
            low = getattr(b, "low", 0)
            dO = getattr(b, "deltaOpen", 0)
            dC = getattr(b, "deltaClose", 0)
            dH = getattr(b, "deltaHigh", 0)

            rows.append({
                "time": pd.Timestamp.fromtimestamp(ts_min * 60, tz="UTC"),
                "open": (low + dO) / 100_000,
                "high": (low + dH) / 100_000,
                "low": low / 100_000,
                "close": (low + dC) / 100_000,
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return None
        df = df.drop_duplicates(subset="time").set_index("time").sort_index()
        # Keep only the requested count (most recent)
        # Use iloc, skip the bars that might be outside our window
        return df.iloc[-(count if len(df) > count else len(df)):].copy()


    def modify_sltp(
        self,
        position_id: int,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        account_id: int | None = None,
        symbol: str | None = None,
    ) -> CtraderOrderResult:
        """Modify SL/TP on an open position for the given account (or primary).

        If *symbol* is provided, absolute SL/TP values are rounded to the
        symbol's decimal digits before sending.
        """
        aid = account_id or self._primary_account
        self._ensure_auth(aid)
        from ctrader_open_api import Protobuf

        # Round to symbol digits if we know the symbol
        digits = self.get_symbol_digits(symbol, account_id=aid) if symbol else 8

        params = {
            "ctidTraderAccountId": aid,
            "positionId": position_id,
        }
        if stop_loss is not None:
            params["stopLoss"] = round(stop_loss, digits)
        if take_profit is not None:
            params["takeProfit"] = round(take_profit, digits)

        if len(params) < 3:
            return CtraderOrderResult(
                message="Must provide stop_loss and/or take_profit",
            )

        req = Protobuf.get("ProtoOAAmendPositionSLTPReq", **params)
        try:
            self._send(req, response_timeout=15.0)
            return CtraderOrderResult(
                order_id=position_id,
                status="modified",
                message=f"SL={stop_loss} TP={take_profit} on account {aid}",
            )
        except Exception as exc:
            return CtraderOrderResult(message=str(exc))


# ---------------------------------------------------------------------------
# Singleton helpers
# ---------------------------------------------------------------------------

_CTRADER_CLIENT: CtraderClient | None = None
_CTRADER_LOCK = threading.Lock()


def get_ctrader(account_ids: list[int] | None = None) -> CtraderClient:
    """Get a cached CtraderClient (connected and authed)."""
    global _CTRADER_CLIENT
    with _CTRADER_LOCK:
        if _CTRADER_CLIENT is not None:
            return _CTRADER_CLIENT
        client = CtraderClient(account_ids=account_ids)
        client.connect()
        _CTRADER_CLIENT = client
        return client


def reset_ctrader():
    """Force re-connect on next get_ctrader."""
    global _CTRADER_CLIENT
    with _CTRADER_LOCK:
        _CTRADER_CLIENT = None
