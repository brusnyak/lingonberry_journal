"""
TradeLocker Data Client
Historical OHLC + live quote polling for forex and commodities.

Symbols use .X suffix: EURUSD.X, XAUUSD.X, GBPUSD.X, etc.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd
from dotenv import load_dotenv

# Load env
load_dotenv()


class TradeLockerError(RuntimeError):
    """Base error for TradeLocker operations."""


class TradeLockerAuthError(TradeLockerError):
    """Authentication or credential error."""


# ---------------------------------------------------------------------------
# Cached TLAPI singletons (demo + live)
# ---------------------------------------------------------------------------

_tlapi_demo: Any = None
_tlapi_live: Any = None
_tlapi_lock = threading.Lock()


def _get_tlapi(environment: str | None = None) -> Any:
    """
    Get or create a cached TLAPI instance for the specified environment.

    Parameters
    ----------
    environment : str, optional
        "demo" or "live". If None, uses TL_ACTIVE_ENV from .env (defaults to "demo").

    Returns
    -------
    TLAPI instance for the requested environment.
    """
    global _tlapi_demo, _tlapi_live

    # Determine which environment to use
    if environment is None:
        environment = os.getenv("TL_ACTIVE_ENV", "demo").lower()

    # Return cached instance if available
    with _tlapi_lock:
        if environment == "demo" and _tlapi_demo is not None:
            return _tlapi_demo
        elif environment == "live" and _tlapi_live is not None:
            return _tlapi_live

        # Create new instance
        try:
            from tradelocker import TLAPI
        except ModuleNotFoundError as exc:
            raise TradeLockerError(
                "tradelocker package not installed. Run: pip install tradelocker"
            ) from exc

        # Load environment-specific credentials
        suffix = environment.upper()
        env = os.getenv(f"TL_ENVIRONMENT_{suffix}", "")
        username = os.getenv(f"TL_USERNAME_{suffix}", "")
        password = os.getenv(f"TL_PASSWORD_{suffix}", "")
        server = os.getenv(f"TL_SERVER_{suffix}", "")

        if not all([env, username, password, server]):
            raise TradeLockerAuthError(
                f"Missing TradeLocker credentials for {environment} environment. "
                f"Set TL_ENVIRONMENT_{suffix}, TL_USERNAME_{suffix}, TL_PASSWORD_{suffix}, "
                f"and TL_SERVER_{suffix} in .env"
            )

        try:
            instance = TLAPI(
                environment=env,
                username=username,
                password=password,
                server=server,
                log_level="warning",
            )
        except Exception as exc:
            raise TradeLockerAuthError(
                f"Failed to authenticate with {environment} environment: {exc}"
            ) from exc

        # Cache the instance
        if environment == "demo":
            _tlapi_demo = instance
        else:
            _tlapi_live = instance

        return instance


# ---------------------------------------------------------------------------
# Symbol resolution
# ---------------------------------------------------------------------------

_INSTRUMENT_CACHE: dict[str, int] = {}
_INSTRUMENT_CACHE_LOCK = threading.Lock()


def resolve_instrument_id(symbol: str) -> int:
    """Resolve a symbol (EURUSD, EURUSD.X, XAUUSD) to TradeLocker instrument ID."""
    clean = symbol.strip().upper()
    if not clean.endswith(".X"):
        clean += ".X"

    with _INSTRUMENT_CACHE_LOCK:
        if clean in _INSTRUMENT_CACHE:
            return _INSTRUMENT_CACHE[clean]

        tl = _get_tlapi()
        try:
            iid = tl.get_instrument_id_from_symbol_name(clean)
        except Exception as exc:
            raise TradeLockerError(f"Cannot resolve symbol {symbol}: {exc}") from exc

        _INSTRUMENT_CACHE[clean] = iid
        return iid


# ---------------------------------------------------------------------------
# Period / resolution helpers
# ---------------------------------------------------------------------------

def _derive_lookback(period: str, limit: int) -> str:
    """Derive a TradeLocker lookback_period from period and limit."""
    import re
    match = re.match(r"(\d+)([mhd])", period.strip().lower())
    if not match:
        return "30D"  # default to generous lookback
    num = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        mins = num * limit
        days = max(mins // 1440, 1)
        return f"{max(days, 7)}D"  # at least 7 days
    elif unit == "h":
        hrs = num * limit
        days = max(hrs // 24, 1)
        return f"{max(days, 14)}D"  # at least 14 days
    else:
        return f"{max(limit, 30)}D"


def _range_lookback(start: datetime, end: datetime) -> str:
    """Derive lookback from a date range. Adds 20% buffer."""
    days = (end - start).total_seconds() / 86400
    days = max(days * 1.2, 7)  # 20% buffer, minimum 7 days
    return f"{int(days)}D"


_TF_TO_TL_PERIOD = {
    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1H", "H4": "4H", "D": "1D", "W": "1W",
}

_TL_PERIOD_TO_TF = {v: k for k, v in _TF_TO_TL_PERIOD.items()}


def _tf_to_tl_period(timeframe: str) -> str:
    p = _TF_TO_TL_PERIOD.get(timeframe.upper())
    if not p:
        raise TradeLockerError(f"Unsupported timeframe: {timeframe}")
    return p


# ---------------------------------------------------------------------------
# Historical OHLC
# ---------------------------------------------------------------------------

def _tl_bars_to_dataframe(bars, period: str) -> pd.DataFrame:
    """Convert TradeLocker bars (DataFrame or list of dicts) to a clean DataFrame."""
    if isinstance(bars, pd.DataFrame):
        df = bars.copy()
    elif isinstance(bars, list) and bars:
        df = pd.DataFrame(bars)
    else:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    if df.empty:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    # TradeLocker TLAPI columns: t (timestamp ms), o, h, l, c, v
    col_map = {"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    required = ["ts", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df["volume"] = df.get("volume", 0.0).fillna(0.0)
    df = df[["ts", "open", "high", "low", "close", "volume"]].dropna(subset=["ts"])
    df = df.sort_values("ts").reset_index(drop=True)

    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["volume"] = df["volume"].astype(float)

    return df


def fetch_historical_bars(
    symbol: str,
    timeframe: str = "M15",
    limit: int = 500,
    lookback: str | None = None,
    environment: str | None = None,
) -> pd.DataFrame:
    """
    Fetch historical OHLC bars from TradeLocker.

    Parameters
    ----------
    symbol : str
        Instrument symbol (EURUSD, XAUUSD, or with .X suffix).
    timeframe : str
        Resolution — M1, M5, M15, M30, H1, H4, D, W.
    limit : int
        Maximum number of bars to return.
    lookback : str, optional
        Explicit lookback period (e.g. "5D", "10h"). Derived from limit if not set.
    environment : str, optional
        "demo" or "live". If None, uses TL_ACTIVE_ENV from .env.

    Returns
    -------
    pd.DataFrame with columns: ts, open, high, low, close, volume
    """
    tl = _get_tlapi(environment)
    iid = resolve_instrument_id(symbol)
    period = _tf_to_tl_period(timeframe)
    if lookback is None:
        lookback = _derive_lookback(period, limit)

    try:
        raw = tl.get_price_history(instrument_id=iid, resolution=period, lookback_period=lookback)
    except Exception as exc:
        raise TradeLockerError(f"Failed to fetch {symbol} {timeframe}: {exc}") from exc

    return _tl_bars_to_dataframe(raw, period)


def fetch_all_timeframes(
    symbol: str,
    timeframes: list[str] | None = None,
    limit: int = 500,
) -> dict[str, pd.DataFrame]:
    """Fetch historical data for multiple timeframes at once."""
    if timeframes is None:
        timeframes = ["M1", "M15", "H1", "H4", "D"]
    return {tf: fetch_historical_bars(symbol, tf, limit) for tf in timeframes}


# ---------------------------------------------------------------------------
# Live quote polling
# ---------------------------------------------------------------------------

_QUOTE_CACHE: dict[int, dict[str, float]] = {}
_QUOTE_CACHE_LOCK = threading.Lock()
_QUOTE_POLLER_THREAD: Optional[threading.Thread] = None
_QUOTE_POLLER_STOP = threading.Event()
_QUOTE_SUBSCRIBERS: dict[int, list[Callable]] = {}
_QUOTE_SUBSCRIBERS_LOCK = threading.Lock()


def get_quote(symbol: str, environment: str | None = None) -> dict[str, float]:
    """
    Get latest bid/ask quote for a symbol.

    Returns dict with keys: bid, ask, bid_size, ask_size, last
    """
    tl = _get_tlapi(environment)
    iid = resolve_instrument_id(symbol)

    try:
        quotes = tl.get_quotes(iid)
        ask_price = tl.get_latest_asking_price(iid)
    except Exception as exc:
        raise TradeLockerError(f"Failed to get quote for {symbol}: {exc}") from exc

    return {
        "bid": float(quotes.get("bp", 0)),
        "ask": float(quotes.get("ap", 0)),
        "bid_size": float(quotes.get("bs", 0)),
        "ask_size": float(quotes.get("as", 0)),
        "last": float(ask_price),
    }


def subscribe_quotes(symbol: str, callback: Callable[[dict[str, float]], None]):
    """Subscribe to live quote updates for a symbol.

    Starts a background poller thread if not already running.
    The callback receives a quote dict whenever the poller detects a change.
    """
    iid = resolve_instrument_id(symbol)
    with _QUOTE_SUBSCRIBERS_LOCK:
        if iid not in _QUOTE_SUBSCRIBERS:
            _QUOTE_SUBSCRIBERS[iid] = []
        _QUOTE_SUBSCRIBERS[iid].append(callback)

    _ensure_poller_running()


def _ensure_poller_running():
    global _QUOTE_POLLER_THREAD
    if _QUOTE_POLLER_THREAD is not None and _QUOTE_POLLER_THREAD.is_alive():
        return

    _QUOTE_POLLER_STOP.clear()
    _QUOTE_POLLER_THREAD = threading.Thread(target=_quote_poller_loop, daemon=True, name="tl-quote-poller")
    _QUOTE_POLLER_THREAD.start()


def _quote_poller_loop():
    """Background loop: poll quotes every 1s for subscribed symbols."""
    poll_interval = float(os.getenv("TL_POLL_INTERVAL", "1.0"))
    tl = _get_tlapi()

    while not _QUOTE_POLLER_STOP.is_set():
        with _QUOTE_SUBSCRIBERS_LOCK:
            iids = list(_QUOTE_SUBSCRIBERS.keys())

        for iid in iids:
            try:
                quotes = tl.get_quotes(iid)
                ask = tl.get_latest_asking_price(iid)
            except Exception:
                continue

            quote = {
                "bid": float(quotes.get("bp", 0)),
                "ask": float(quotes.get("ap", 0)),
                "bid_size": float(quotes.get("bs", 0)),
                "ask_size": float(quotes.get("as", 0)),
                "last": float(ask),
            }

            with _QUOTE_CACHE_LOCK:
                _QUOTE_CACHE[iid] = quote

            # Notify subscribers
            with _QUOTE_SUBSCRIBERS_LOCK:
                for cb in _QUOTE_SUBSCRIBERS.get(iid, []):
                    try:
                        cb(quote)
                    except Exception:
                        pass

        time.sleep(poll_interval)


def stop_quote_poller():
    """Stop the background quote poller thread."""
    _QUOTE_POLLER_STOP.set()


# ---------------------------------------------------------------------------
# Order Execution (Paper Trading on Demo)
# ---------------------------------------------------------------------------

def create_order(
    symbol: str,
    quantity: float,
    side: str,
    order_type: str = "market",
    price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    account_number: int | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """
    Create a trade order on TradeLocker.

    Parameters
    ----------
    symbol : str
        Instrument symbol (EURUSD, GBPUSD.X, etc.)
    quantity : float
        Lot size (e.g. 0.01 for micro lot)
    side : str
        "buy" or "sell"
    order_type : str
        "market", "limit", or "stop"
    price : float, optional
        Required for limit/stop orders
    stop_loss : float, optional
        Stop loss price
    take_profit : float, optional
        Take profit price
    account_number : int, optional
        TradeLocker account number (reserved for future use)
    environment : str, optional
        "demo" or "live". If None, uses TL_ACTIVE_ENV from .env.

    Returns
    -------
    dict with keys: order_id, status, message
    """
    tl = _get_tlapi(environment)
    iid = resolve_instrument_id(symbol)

    try:
        # Create the order
        order_id = tl.create_order(
            instrument_id=iid,
            quantity=quantity,
            side=side,
            type_=order_type,
            price=price,
            stop_loss=stop_loss,
            stop_loss_type="absolute" if stop_loss else None,
            take_profit=take_profit,
            take_profit_type="absolute" if take_profit else None,
        )

        if order_id:
            return {
                "order_id": order_id,
                "status": "filled" if order_type == "market" else "pending",
                "message": f"Order placed: {side} {quantity} {symbol} @ {price or 'market'}",
            }
        else:
            return {
                "order_id": None,
                "status": "failed",
                "message": "TradeLocker returned no order_id",
            }

    except Exception as exc:
        return {
            "order_id": None,
            "status": "error",
            "message": str(exc),
        }


def close_position(
    order_id: int,
    account_number: int | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """
    Close an open position by order ID.

    Parameters
    ----------
    order_id : int
        The order ID to close
    account_number : int, optional
        TradeLocker account number (reserved for future use)
    environment : str, optional
        "demo" or "live". If None, uses TL_ACTIVE_ENV from .env.

    Returns
    -------
    dict with keys: status, message
    """
    tl = _get_tlapi(environment)

    try:
        tl.close_position(order_id)
        return {
            "status": "closed",
            "message": f"Position {order_id} closed",
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
        }


def modify_position(
    order_id: int,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    account_number: int | None = None,
) -> dict[str, Any]:
    """
    Modify SL/TP on an open position.

    Parameters
    ----------
    order_id : int
        The order ID to modify
    stop_loss : float, optional
        New stop loss price
    take_profit : float, optional
        New take profit price
    account_number : int, optional
        TradeLocker account number (reserved for future use)

    Returns
    -------
    dict with keys: status, message
    """
    tl = _get_tlapi()

    try:
        tl.modify_position(
            order_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        return {
            "status": "modified",
            "message": f"Position {order_id} modified: SL={stop_loss}, TP={take_profit}",
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
        }


def get_open_positions(
    account_number: int | None = None,
) -> list[dict[str, Any]]:
    """
    Get all open positions for an account.

    Returns
    -------
    list of dicts with keys: order_id, symbol, side, quantity, entry_price,
                             current_price, pnl, stop_loss, take_profit
    """
    tl = _get_tlapi()

    try:
        positions_df = tl.get_all_positions()
        if positions_df is None or positions_df.empty:
            return []

        result = []
        for _, pos in positions_df.iterrows():
            # Get symbol name from instrument ID
            try:
                iid = pos.get("tradableInstrumentId")
                if iid:
                    symbol = tl.get_symbol_name_from_instrument_id(iid)
                    quote = tl.get_quotes(iid)
                    current_price = float(quote.get("bp", 0)) if quote else 0
                else:
                    symbol = ""
                    current_price = 0
            except Exception:
                symbol = ""
                current_price = 0

            result.append({
                "order_id": pos.get("id"),
                "symbol": symbol,
                "side": pos.get("side", ""),
                "quantity": float(pos.get("qty", 0)),
                "entry_price": float(pos.get("avgPrice", 0)),
                "current_price": current_price,
                "pnl": float(pos.get("unrealizedPl", 0)),
                "stop_loss_id": pos.get("stopLossId"),
                "take_profit_id": pos.get("takeProfitId"),
                "open_date": pos.get("openDate"),
            })
        return result

    except Exception as exc:
        print(f"Error getting positions: {exc}")
        return []


def get_account_balance(
    account_number: int | None = None,
) -> dict[str, Any]:
    """
    Get account balance and equity.

    Returns
    -------
    dict with keys: balance, equity, margin, free_margin, margin_level
    """
    tl = _get_tlapi()

    try:
        state = tl.get_account_state()
        return {
            "balance": float(state.get("balance", 0)),
            "equity": float(state.get("projectedBalance", 0)),
            "margin": float(state.get("initialMarginReq", 0)),
            "free_margin": float(state.get("availableFunds", 0)),
            "margin_level": None,
            "open_positions": int(state.get("positionsCount", 0)),
            "open_orders": int(state.get("ordersCount", 0)),
            "today_pnl": float(state.get("todayNet", 0)),
        }
    except Exception as exc:
        return {
            "balance": 0,
            "equity": 0,
            "margin": 0,
            "free_margin": 0,
            "margin_level": None,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Save to market_data cache
# ---------------------------------------------------------------------------

LOCAL_MARKET_DIR = Path("data/market_data")


def save_to_local(df: pd.DataFrame, symbol: str, timeframe: str):
    """Save fetched data to local market_data cache."""
    if df.empty:
        return
    try:
        asset_type = "forex"
        if symbol.upper().startswith("XAU") or symbol.upper().startswith("XAG"):
            asset_type = "commodity"
        output_dir = LOCAL_MARKET_DIR / asset_type / symbol.upper()
        output_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_dir / f"{timeframe.lower()}.csv", index=False)
    except Exception as e:
        print(f"Warning: Could not save to market_data: {e}")
