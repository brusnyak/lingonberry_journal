#!/usr/bin/env python3
"""
Economic Calendar / News Filter

Two modes:
  1. Heuristic (always available) — known high-impact release windows per currency.
     Uses the established weekly/monthly schedule of major economic data releases.
  2. Live feed (when available) — fetches ForexFactory JSON calendar for precise
     event-based blocking. Falls back to heuristic if the feed is unreachable.

For both modes: maps a symbol (e.g. "GBPAUD") to its constituent currencies,
then checks if any high-impact event is within the caution window for that currency.

Usage:
    from infra.news_calendar import is_news_caution, get_active_events

    if is_news_caution("GBPAUD", some_timestamp):
        # skip trade entry
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heuristic: known high-impact economic release windows (UTC)
# Format: list of (start_hour, start_minute, end_hour, end_minute) tuples
# Each window is a ~30-minute block where the release + initial volatility
# is expected. These are the standard release times for major data.
# ---------------------------------------------------------------------------

# USD: NFP, CPI, GDP, Retail Sales, Durable Goods, etc.
#   8:30 AM ET  = 12:30 UTC (winter) / 13:30 UTC (summer)
#   We use summer hours (EDT) as default since most of the trading year is EDT
#   10:00 AM ET = 14:00 UTC — ISM, Michigan, JOLTS
#   2:00 PM ET  = 18:00 UTC — FOMC minutes/projections
_USD_NEWS: List[Tuple[int, int, int, int]] = [
    (12, 25, 13,  0),   # 8:25-9:00 AM ET  — NFP, CPI, GDP, Retail Sales
    (13, 55, 14, 30),   # 9:55-10:30 AM ET — ISM, Michigan, JOLTS
    (17, 55, 18, 30),   # 1:55-2:30 PM ET  — FOMC minutes
]

# EUR: ECB decision, German data, Eurozone CPI
#   ECB rate decision: 12:15 UTC (summer) / 13:15 UTC (winter)
#   German data: 07:00, 08:00, 09:00 UTC
#   Eurozone CPI, PMI: 09:00, 10:00 UTC
_EUR_NEWS: List[Tuple[int, int, int, int]] = [
    ( 6, 55,  7, 30),   # 7:00-7:30 — German trade/industrial production
    ( 8, 55,  9, 30),   # 9:00-9:30 — Eurozone CPI (preliminary)
    ( 9, 55, 10, 30),   # 10:00-10:30 — Eurozone economic data
    (11, 45, 12, 30),   # 11:45-12:30 — ECB rate decision & presser start
]

# GBP: BOE decision, UK CPI, Employment, Retail Sales
#   BOE: 11:00 UTC (summer) / 12:00 UTC (winter) — decision + minutes + inflation report
#   UK data drops: 07:00 UTC — CPI, Employment, GDP, Retail Sales
_GBP_NEWS: List[Tuple[int, int, int, int]] = [
    ( 6, 55,  7, 30),   # 7:00-7:30 — UK CPI, Employment, Retail Sales, GDP
    (10, 55, 11, 30),   # 11:00-11:30 — BOE rate decision
]

# JPY: BOJ decision, CPI, GDP, Tankan
#   BOJ: roughly 03:00-06:00 UTC depending on meeting
#   Key data: 23:50, 00:30, 01:30, 05:00, 07:00 UTC
_JPY_NEWS: List[Tuple[int, int, int, int]] = [
    (23, 40,  0, 20),   # 23:50 — Trade, Industrial Production
    ( 0, 25,  1,  0),   # 0:30 — BOJ Summary of Opinions
    ( 1, 25,  2,  0),   # 1:30 — CPI Tokyo
    ( 4, 55,  5, 30),   # 5:00 — Leading Index
]

# AUD: RBA decision, Employment, CPI, Retail Sales
#   RBA: 03:30 UTC (summer) / 04:30 UTC (winter)
#   Employment: 00:30 UTC
#   CPI: 01:30 UTC
_AUD_NEWS: List[Tuple[int, int, int, int]] = [
    ( 0, 25,  1,  0),   # 0:30 — Employment
    ( 1, 25,  2,  0),   # 1:30 — CPI
    ( 3, 25,  4,  0),   # 3:30 — RBA rate decision
]

# NZD: RBNZ decision, Employment, GDP
#   RBNZ: 21:00-22:00 UTC (varies)
#   Employment: 21:45 UTC
_NZD_NEWS: List[Tuple[int, int, int, int]] = [
    (20, 45, 21, 30),   # 20:45 — Employment, CPI
    (20, 55, 21, 30),   # 21:00 — RBNZ rate decision
]

# CAD: BOC decision, Employment, CPI, Retail Sales
#   Employment: 12:30 UTC
#   CPI: 12:30 UTC
#   BOC: 14:00 UTC
#   Note: many CAD releases overlap USD 8:30 ET window
_CAD_NEWS: List[Tuple[int, int, int, int]] = [
    (12, 25, 13,  0),   # 12:30 — Employment, CPI, Retail Sales
    (13, 55, 14, 30),   # 14:00 — BOC rate decision
]

# CHF: SNB decision, CPI, Trade
#   SNB: 07:30 UTC (summer) / 08:30 UTC (winter)
#   CPI: 06:00-07:00 UTC (varies)
_CHF_NEWS: List[Tuple[int, int, int, int]] = [
    ( 5, 55,  6, 30),   # 6:00-7:00 — CPI, Trade
    ( 7, 25,  8,  0),   # 7:30 — SNB rate decision
]

# Map currency → known news windows
_CURRENCY_NEWS: Dict[str, List[Tuple[int, int, int, int]]] = {
    "USD": _USD_NEWS,
    "EUR": _EUR_NEWS,
    "GBP": _GBP_NEWS,
    "JPY": _JPY_NEWS,
    "AUD": _AUD_NEWS,
    "NZD": _NZD_NEWS,
    "CAD": _CAD_NEWS,
    "CHF": _CHF_NEWS,
}

# ---------------------------------------------------------------------------
# Symbol → currency decomposition
# e.g. "GBPAUD" → ["GBP", "AUD"],  "EURUSD" → ["EUR", "USD"]
# JPY pairs are exceptions: USDJPY → ["USD", "JPY"] not ["US", "DJ", "PY"]
# ---------------------------------------------------------------------------

# Pairs where the first 3 chars are the base and last 3 are the quote
_FOREX_CURRENCIES = {
    "EUR", "GBP", "USD", "JPY", "AUD", "NZD", "CAD", "CHF",
}

# When the first currency is 2-letter (e.g. "GBPJPY" is "GBP"+"JPY", not "GB"+"PJ")
# We just split by known 3-letter codes
def currencies_for_symbol(symbol: str) -> List[str]:
    """Return the currencies involved in a forex symbol.
    
    >>> currencies_for_symbol("GBPAUD")
    ["GBP", "AUD"]
    >>> currencies_for_symbol("EURUSD")
    ["EUR", "USD"]
    >>> currencies_for_symbol("XAUUSD")
    ["USD"]  # commodities primarily affected by USD
    """
    clean = symbol.upper().replace(".X", "").replace("/", "")
    
    # Commodities and indices — primarily affected by USD
    if clean in ("XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "USOIL", "UKOIL"):
        return ["USD"]
    if clean in ("US30", "US100", "NAS100", "SPX500", "US500"):
        return ["USD"]
    if clean.startswith("BTC") or clean.startswith("ETH"):
        return ["USD"]
    
    # Forex pairs: split 3+3
    if len(clean) == 6:
        base = clean[:3]
        quote = clean[3:]
        currencies = []
        if base in _FOREX_CURRENCIES:
            currencies.append(base)
        if quote in _FOREX_CURRENCIES:
            currencies.append(quote)
        return currencies
    
    return []


# ---------------------------------------------------------------------------
# Live ForexFactory feed (cached)
# ---------------------------------------------------------------------------

_FF_CACHE: Optional[List[Dict]] = None
_FF_CACHE_TIME: Optional[datetime] = None
_FF_CACHE_LOCK = threading.Lock()
_FF_CACHE_TTL = timedelta(hours=2)  # fresh for 2 hours


def _fetch_forexfactory() -> Optional[List[Dict]]:
    """Fetch economic calendar from ForexFactory JSON feed.
    
    Returns list of events or None if feed is unavailable.
    Each event has keys: date, currency, impact, title, forecast, previous
    """
    global _FF_CACHE, _FF_CACHE_TIME
    
    with _FF_CACHE_LOCK:
        now = datetime.now(timezone.utc)
        if _FF_CACHE is not None and _FF_CACHE_TIME is not None:
            if now - _FF_CACHE_TIME < _FF_CACHE_TTL:
                return _FF_CACHE
    
    try:
        import requests
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; TradingBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            events = resp.json()
            # Filter to high-impact only
            high_impact = [
                e for e in events
                if str(e.get("impact", "")).lower() in ("high", "h")
            ]
            with _FF_CACHE_LOCK:
                _FF_CACHE = high_impact
                _FF_CACHE_TIME = now
            logger.info("Fetched %d high-impact events from ForexFactory", len(high_impact))
            return high_impact
        else:
            logger.warning("ForexFactory feed returned %d", resp.status_code)
            return None
    except Exception as exc:
        logger.debug("ForexFactory feed unavailable: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

# Configurable caution window in minutes before/after the event
CAUTION_WINDOW_MINUTES = int(os.getenv("NEWS_CAUTION_WINDOW", "30"))


def _in_heuristic_window(ts: datetime, currency: str) -> bool:
    """Check if timestamp falls within any known news window for the currency."""
    windows = _CURRENCY_NEWS.get(currency.upper())
    if not windows:
        return False
    
    h = ts.hour
    m = ts.minute
    hm = h * 60 + m  # minutes since midnight
    
    for start_h, start_m, end_h, end_m in windows:
        start = start_h * 60 + start_m
        end = end_h * 60 + end_m
        if start <= hm < end:
            return True
    return False


def _in_live_feed_window(ts: datetime, currency: str) -> bool:
    """Check if timestamp is within caution window of any high-impact event for the currency."""
    events = _fetch_forexfactory()
    if not events:
        return False  # feed unavailable, don't block on live data
    
    window = timedelta(minutes=CAUTION_WINDOW_MINUTES)
    
    for event in events:
        if str(event.get("currency", "")).upper() != currency.upper():
            continue
        
        try:
            event_dt = datetime.fromisoformat(event["date"])
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
        except (ValueError, KeyError):
            continue
        
        if abs((ts - event_dt).total_seconds()) <= window.total_seconds():
            return True
    
    return False


def is_news_caution(
    symbol: str,
    ts: Optional[datetime] = None,
    use_live_feed: bool = True,
) -> bool:
    """Check if we should avoid trading a symbol at the given timestamp due to news.
    
    Args:
        symbol: Trading symbol (e.g. "GBPAUD", "EURUSD")
        ts: Timestamp to check (default: now UTC)
        use_live_feed: Try ForexFactory feed first; fall back to heuristic
    
    Returns:
        True if a high-impact news event is active for this symbol
    """
    if ts is None:
        ts = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    
    currencies = currencies_for_symbol(symbol)
    if not currencies:
        return False
    
    for currency in currencies:
        if use_live_feed:
            # Try live feed first — if it returns data, use it
            live_result = _in_live_feed_window(ts, currency)
            if live_result:
                return True
        
        # Fall back to heuristic always (works for backtesting, no external deps)
        if _in_heuristic_window(ts, currency):
            return True
    
    return False


def get_active_events(
    symbol: str,
    ts: Optional[datetime] = None,
) -> List[Dict]:
    """Return active high-impact events for a symbol at the given timestamp.
    
    Returns empty list if no events or feed unavailable.
    Each dict has keys: date, currency, impact, title
    """
    if ts is None:
        ts = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    
    currencies = currencies_for_symbol(symbol)
    if not currencies:
        return []
    
    events = _fetch_forexfactory()
    if not events:
        return []
    
    window = timedelta(minutes=CAUTION_WINDOW_MINUTES)
    active = []
    
    for event in events:
        if str(event.get("currency", "")).upper() not in currencies:
            continue
        
        try:
            event_dt = datetime.fromisoformat(event["date"])
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
        except (ValueError, KeyError):
            continue
        
        if abs((ts - event_dt).total_seconds()) <= window.total_seconds():
            active.append({
                "date": event["date"],
                "currency": event.get("currency", ""),
                "impact": event.get("impact", ""),
                "title": event.get("title", ""),
            })
    
    return active


def get_next_events(symbol: str, limit: int = 5) -> List[Dict]:
    """Get the next N high-impact events for a symbol."""
    currencies = currencies_for_symbol(symbol)
    if not currencies:
        return []
    
    events = _fetch_forexfactory()
    if not events:
        return []
    
    now = datetime.now(timezone.utc)
    relevant = []
    
    for event in events:
        if str(event.get("currency", "")).upper() not in currencies:
            continue
        try:
            event_dt = datetime.fromisoformat(event["date"])
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
        except (ValueError, KeyError):
            continue
        if event_dt > now:
            relevant.append({
                "date": event["date"],
                "currency": event.get("currency", ""),
                "impact": event.get("impact", ""),
                "title": event.get("title", ""),
            })
    
    return relevant[:limit]
