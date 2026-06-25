#!/usr/bin/env python3
"""Mean Reversion Live Trading Bot — mirrors backtested v1 strategy on TradeLocker.

Strategy (matches MeanReversionStrategy backtest):
  Entry  : last closed 1m bar close < SMA(29)  →  buy market
  Exit   : last closed 1m bar close > SMA(29)  →  close long
  Stop   : server-side SL placed at entry × (1 − stop_pct)

Runs indefinitely, checking every minute (synced to minute boundary + POLL_DELAY).
Designed to run as a systemd service (see deploy/systemd/journal-mr-bot.service.template).

Environment variables
---------------------
  TL_ENVIRONMENT   TradeLocker URL  (default: https://live.tradelocker.com)
  TL_USERNAME      Email
  TL_PASSWORD      Password
  TL_SERVER        Server name (e.g. GFTTL for Goat Funded Trader)
  TL_ACCOUNT_ID    Account ID (0 = auto-select first account)

  BOT_PAIRS        Comma-separated symbols, e.g. "GBPAUD,AUDCHF,EURAUD"
  BOT_RISK_PCT     Fraction of equity risked per trade  (default: 0.01 = 1%)
  BOT_STOP_PCT     Hard stop distance from entry price  (default: 0.015 = 1.5%)
  BOT_SMA_PERIOD   SMA period                           (default: 29)
  BOT_LOT_STEP     Minimum lot increment                (default: 0.05)
  BOT_MAX_LOTS     Maximum lots per order               (default: 20.0)
  BOT_POLL_DELAY   Seconds past the minute to poll      (default: 5)
  BOT_DRY_RUN      "true" → log signals, never place orders
"""
from __future__ import annotations

import logging
import math
import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("mr-bot")

import pandas as pd

# ── Config ───────────────────────────────────────────────────────────────────

PAIRS      = [p.strip().upper() for p in os.getenv("BOT_PAIRS", "GBPAUD").split(",") if p.strip()]
RISK_PCT   = float(os.getenv("BOT_RISK_PCT",   "0.01"))
STOP_PCT   = float(os.getenv("BOT_STOP_PCT",   "0.015"))
SMA_PERIOD = int(os.getenv("BOT_SMA_PERIOD",   "29"))
LOT_STEP   = float(os.getenv("BOT_LOT_STEP",   "0.05"))
MAX_LOTS   = float(os.getenv("BOT_MAX_LOTS",   "20.0"))
POLL_DELAY = int(os.getenv("BOT_POLL_DELAY",   "5"))
DRY_RUN    = os.getenv("BOT_DRY_RUN", "false").lower() == "true"

# JPY pairs: 1 pip ≈ 0.01 in price terms; contract mult is 1k not 100k
_JPY_PAIRS = {"EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "USDJPY"}

# ── TLAPI singleton ──────────────────────────────────────────────────────────

_tl = None


def get_tl():
    global _tl
    if _tl is not None:
        return _tl
    from tradelocker import TLAPI
    env      = os.getenv("TL_ENVIRONMENT", "https://demo.tradelocker.com")
    username = os.getenv("TL_USERNAME", "")
    password = os.getenv("TL_PASSWORD", "")
    server   = os.getenv("TL_SERVER", "")
    # TL_ACC_NUM is the account ID shown in the TradeLocker UI (#2165806 / #2165807)
    # These map to the "id" column in TLAPI, so we pass as account_id (not acc_num)
    account_id = int(os.getenv("TL_ACC_NUM", "0"))

    if not all([username, password, server]):
        raise RuntimeError("Missing TL_USERNAME / TL_PASSWORD / TL_SERVER in environment")

    _tl = TLAPI(environment=env, username=username, password=password,
                server=server, account_id=account_id, log_level="warning")
    log.info("Connected to TradeLocker  env=%s  account_id=%s  acc_num=%s",
             env, _tl.account_id, _tl.acc_num)
    return _tl


# ── Instrument ID cache ──────────────────────────────────────────────────────

_id_cache: dict[str, int] = {}


def resolve_id(symbol: str) -> int:
    if symbol not in _id_cache:
        tl = get_tl()
        clean = symbol.upper()
        if not clean.endswith(".X"):
            clean += ".X"
        _id_cache[symbol] = tl.get_instrument_id_from_symbol_name(clean)
    return _id_cache[symbol]


# ── Position sizing ──────────────────────────────────────────────────────────

def calc_lots(equity: float, stop_dist: float, is_jpy: bool) -> float:
    """Risk-based lot sizing (mirrors _calc_size in MeanReversionStrategy)."""
    mult     = 1_000 if is_jpy else 100_000
    risk_amt = equity * RISK_PCT
    if stop_dist <= 0:
        return LOT_STEP
    raw_lots = (risk_amt / stop_dist) / mult
    size     = round(math.floor(raw_lots / LOT_STEP) * LOT_STEP, 2)
    return max(min(size, MAX_LOTS), LOT_STEP)


# ── Account ──────────────────────────────────────────────────────────────────

def get_equity() -> float:
    state = get_tl().get_account_state()
    # TradeLocker returns various key names; try common ones
    for key in ("equity", "Equity", "balance", "Balance"):
        if key in state:
            return float(state[key])
    # Fallback: sum of values if it's a list
    log.warning("equity key not found in account state, keys=%s", list(state.keys()))
    return 0.0


# ── Positions ────────────────────────────────────────────────────────────────

def get_open_position(instrument_id: int) -> dict | None:
    """Return open long position for this instrument, or None."""
    df = get_tl().get_all_positions()
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return None
    # Find column that holds instrument ID
    id_col = next((c for c in df.columns
                   if "instrument" in c.lower() or "tradable" in c.lower()), None)
    if id_col is None:
        return None
    matches = df[df[id_col] == instrument_id]
    if matches.empty:
        return None
    row = matches.iloc[0].to_dict()
    return row


def get_position_id(position: dict) -> int:
    for k, v in position.items():
        if "positionid" in k.lower() or k.lower() == "id":
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    return 0


# ── Market data ──────────────────────────────────────────────────────────────

def fetch_bars(symbol: str, n_bars: int = 60) -> pd.DataFrame:
    """Fetch last n_bars 1m bars. Returns DataFrame with close column."""
    tl  = get_tl()
    iid = resolve_id(symbol)
    try:
        raw = tl.get_price_history(instrument_id=iid, resolution="1m", lookback_period="2D")
    except Exception as exc:
        log.error("%s  fetch_bars failed: %s", symbol, exc)
        return pd.DataFrame()

    if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
        return pd.DataFrame()

    df = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame(raw)
    col_map = {"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        df = df.sort_values("ts")

    if "close" not in df.columns:
        log.error("%s  no close column in bars: %s", symbol, df.columns.tolist())
        return pd.DataFrame()

    df["close"] = df["close"].astype(float)
    return df.tail(n_bars).reset_index(drop=True)


# ── Strategy signal ──────────────────────────────────────────────────────────

def compute_signal(df: pd.DataFrame) -> tuple[str, float, float]:
    """
    Returns (signal, last_close, sma_value).
    signal: 'buy' | 'sell' | 'hold'

    Uses iloc[-1] (last fully closed bar) — we poll 5 s after the minute
    so the previous candle is sealed.
    """
    if len(df) < SMA_PERIOD + 1:
        return "hold", 0.0, 0.0

    sma   = df["close"].rolling(SMA_PERIOD).mean()
    close = float(df["close"].iloc[-1])
    sma_v = float(sma.iloc[-1])

    if close < sma_v:
        return "buy", close, sma_v
    elif close > sma_v:
        return "sell", close, sma_v
    return "hold", close, sma_v


# ── Order execution ──────────────────────────────────────────────────────────

def place_buy(symbol: str, instrument_id: int, equity: float, close: float) -> bool:
    is_jpy    = symbol in _JPY_PAIRS
    stop_dist = close * STOP_PCT
    lots      = calc_lots(equity, stop_dist, is_jpy)
    sl_price  = round(close * (1.0 - STOP_PCT), 5)

    log.info("BUY  %s  close=%.5f  lots=%.2f  SL=%.5f  (equity=%.2f  risk=%.1f%%)",
             symbol, close, lots, sl_price, equity, RISK_PCT * 100)

    if DRY_RUN:
        log.info("[DRY RUN] order not sent")
        return True

    try:
        order_id = get_tl().create_order(
            instrument_id=instrument_id,
            quantity=lots,
            side="buy",
            type_="market",
            stop_loss=sl_price,
            stop_loss_type="absolute",
        )
        if order_id:
            log.info("BUY  %s  order_id=%s", symbol, order_id)
            return True
        log.error("BUY  %s  create_order returned None", symbol)
        return False
    except Exception as exc:
        log.error("BUY  %s  failed: %s", symbol, exc)
        return False


def close_long(symbol: str, position: dict, close: float) -> bool:
    pos_id = get_position_id(position)
    log.info("CLOSE %s  close=%.5f  pos_id=%s", symbol, close, pos_id)

    if DRY_RUN:
        log.info("[DRY RUN] close not sent")
        return True

    if not pos_id:
        log.error("CLOSE %s  could not determine position ID from %s", symbol, list(position.keys()))
        return False

    try:
        ok = get_tl().close_position(position_id=pos_id)
        if ok:
            log.info("CLOSE %s  success", symbol)
        else:
            log.warning("CLOSE %s  returned False", symbol)
        return bool(ok)
    except Exception as exc:
        log.error("CLOSE %s  failed: %s", symbol, exc)
        return False


# ── Main loop ────────────────────────────────────────────────────────────────

def tick():
    equity = get_equity()
    if equity <= 0:
        log.warning("equity=%.2f — skipping tick", equity)
        return

    for symbol in PAIRS:
        try:
            iid      = resolve_id(symbol)
            df       = fetch_bars(symbol)
            if df.empty:
                log.warning("%s  no bar data", symbol)
                continue

            signal, close, sma = compute_signal(df)
            position            = get_open_position(iid)
            is_long             = position is not None

            log.info("%s  close=%.5f  sma=%.5f  signal=%-4s  pos=%s",
                     symbol, close, sma, signal, "LONG" if is_long else "FLAT")

            if signal == "buy" and not is_long:
                place_buy(symbol, iid, equity, close)
            elif signal == "sell" and is_long:
                close_long(symbol, position, close)

        except Exception as exc:
            log.error("%s  tick error: %s", symbol, exc)


def sleep_to_next_minute():
    """Sleep until POLL_DELAY seconds past the next whole minute."""
    now    = time.time()
    remain = 60 - (now % 60) + POLL_DELAY
    if remain > 60:
        remain -= 60
    log.debug("sleeping %.1f s to next poll", remain)
    time.sleep(remain)


def main():
    if DRY_RUN:
        log.info("*** DRY RUN — signals will be logged but NO orders placed ***")

    log.info("Mean Reversion Bot | pairs=%s  risk=%.1f%%  stop=%.1f%%  sma=%d",
             PAIRS, RISK_PCT * 100, STOP_PCT * 100, SMA_PERIOD)

    # Resolve IDs on startup so first tick is fast
    for sym in PAIRS:
        try:
            iid = resolve_id(sym)
            log.info("Resolved %s → instrument_id=%s", sym, iid)
        except Exception as exc:
            log.error("Cannot resolve %s: %s — pair will be skipped until retry", sym, exc)

    while True:
        sleep_to_next_minute()
        try:
            tick()
        except Exception as exc:
            log.error("Unhandled tick error: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()
