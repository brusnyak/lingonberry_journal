"""
Crypto structural-analysis watchlist — the read-only "overlay" for manual
oversight, per the 2026-07-18 request: show the analysis so a human can
apply their own judgment and execute manually, not an auto-trading bot.

Reuses backtesting.structure_lib exclusively (the pipeline validated all
session on real BingX data) -- NOT webapp/app.py's separate `pine/backend`
structure module, which is a different, unvalidated implementation for FX.

Public market data only (BingX public REST via ccxt/engine.data) -- no API
key needed for this page. Account balance/positions overlay comes later,
once a real API key exists and is confirmed demo/zero-risk.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ccxt

from backtesting.engine.data import load_data
from backtesting.structure_lib.swing import swing_points
from backtesting.structure_lib.labels import label_structure

_ccxt_client: ccxt.bingx | None = None


def _client() -> ccxt.bingx:
    global _ccxt_client
    if _ccxt_client is None:
        _ccxt_client = ccxt.bingx({"options": {"defaultType": "swap"}})  # public data only, no keys needed
    return _ccxt_client


def _derivatives_context(symbol: str) -> dict:
    """Current OI + funding rate, free via BingX's own API (no CoinGlass
    needed for a live snapshot -- only for OI *history*, which BingX/ccxt
    doesn't expose). Best-effort: never blocks the structural read."""
    ccxt_symbol = symbol[:-4] + "/USDT:USDT" if symbol.endswith("USDT") else symbol
    out = {"open_interest_usd": None, "funding_rate": None}
    try:
        oi = _client().fetch_open_interest(ccxt_symbol)
        out["open_interest_usd"] = oi.get("openInterestValue")
    except Exception:
        pass
    try:
        fr = _client().fetch_funding_rate(ccxt_symbol)
        out["funding_rate"] = fr.get("fundingRate")
    except Exception:
        pass
    return out
from backtesting.structure_lib.fvg import detect_fvgs

DEFAULT_WATCHLIST = [
    "AKEUSDT", "PUMPUSDT", "BOMEUSDT", "1000BONKUSDT", "TOSHIUSDT", "HOMEUSDT",
    "DOGEUSDT", "XRPUSDT", "SOLUSDT",
]


def snapshot(symbol: str, exchange: str = "bingx") -> dict:
    """One pair's current structural read: HTF/LTF trend, nearest FVG,
    structural stop reference. Mirrors the manual analysis done in-session
    on AKE/1000BONK/etc, just made repeatable and servable."""
    try:
        df240 = load_data(symbol, tf="240", exchange=exchange)
        df15 = load_data(symbol, tf="15", exchange=exchange)
        if df240.empty or len(df240) < 20 or df15.empty or len(df15) < 20:
            return {"symbol": symbol, "error": "insufficient data"}
        df240 = df240.sort_values("ts").reset_index(drop=True)
        df15 = df15.sort_values("ts").reset_index(drop=True)

        sw240, lv240 = swing_points(df240, swing_length=3, causal=True)
        lab240 = label_structure(df240, sw240, lv240)
        htf_trend = str(lab240["trend"].iloc[-1])

        recent = df15.tail(300).reset_index(drop=True)
        sw15, lv15 = swing_points(recent, swing_length=3, causal=True)
        lab15 = label_structure(recent, sw15, lv15)
        ltf_trend = str(lab15["trend"].iloc[-1])
        last_price = float(recent["close"].iloc[-1])
        last_ts = recent["ts"].iloc[-1].isoformat()

        lbl = lab15[lab15["structure_label"] != ""]
        stop_ref = None
        stop_kind = None
        if ltf_trend == "bullish":
            hl = lbl[lbl["structure_label"] == "HL"]
            if not hl.empty:
                stop_ref = float(recent["low"].iloc[hl.index[-1]])
                stop_kind = "behind last HL"
        elif ltf_trend == "bearish":
            lh = lbl[lbl["structure_label"] == "LH"]
            if not lh.empty:
                stop_ref = float(recent["high"].iloc[lh.index[-1]])
                stop_kind = "behind last LH"

        fvgs = detect_fvgs(recent)
        bull_fvgs = [f for f in fvgs if f.kind == "bullish"]
        bear_fvgs = [f for f in fvgs if f.kind == "bearish"]
        nearest = None
        if ltf_trend == "bullish" and bull_fvgs:
            f = bull_fvgs[-1]
            nearest = {"kind": f.kind, "top": f.top, "bottom": f.bottom, "ce": f.ce}
        elif ltf_trend == "bearish" and bear_fvgs:
            f = bear_fvgs[-1]
            nearest = {"kind": f.kind, "top": f.top, "bottom": f.bottom, "ce": f.ce}

        aligned = htf_trend == ltf_trend and htf_trend in ("bullish", "bearish")
        deriv = _derivatives_context(symbol)

        return {
            "symbol": symbol,
            "price": last_price,
            "as_of": last_ts,
            "htf_trend": htf_trend,
            "ltf_trend": ltf_trend,
            "aligned": aligned,
            "nearest_fvg": nearest,
            "stop_ref": stop_ref,
            "stop_kind": stop_kind,
            "open_interest_usd": deriv["open_interest_usd"],
            "funding_rate": deriv["funding_rate"],
            "error": None,
        }
    except Exception as e:
        return {"symbol": symbol, "error": f"{type(e).__name__}: {e}"}


def watchlist_snapshot(symbols: list[str] | None = None) -> list[dict]:
    return [snapshot(s) for s in (symbols or DEFAULT_WATCHLIST)]
