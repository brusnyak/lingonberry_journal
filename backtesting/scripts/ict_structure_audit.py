#!/usr/bin/env python3
"""Audit strict ICT structure and compare with smartmoneyconcepts when installed."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.engine.data import load_data  # noqa: E402
from backtesting.features.ict_structure import IctStructureConfig, build_ict_structure_index  # noqa: E402


def asset_type_for(symbol: str) -> str:
    if symbol == "XAUUSD":
        return "commodity"
    if symbol == "NAS100":
        return "index"
    return "forex"


def smc_summary(df: pd.DataFrame, swing_length: int) -> dict:
    try:
        from smartmoneyconcepts import smc
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    ohlc = df[["open", "high", "low", "close"]].copy()
    swings = smc.swing_highs_lows(ohlc, swing_length=swing_length)
    bos = smc.bos_choch(ohlc, swings, close_break=True)
    return {
        "available": True,
        "swings": int(swings["HighLow"].notna().sum()),
        "swing_highs": int((swings["HighLow"] == 1).sum()),
        "swing_lows": int((swings["HighLow"] == -1).sum()),
        "bos": int(bos["BOS"].notna().sum()) if "BOS" in bos else 0,
        "choch": int(bos["CHOCH"].notna().sum()) if "CHOCH" in bos else 0,
        "note": "SMC swing labels are placed at pivot bars; shift by swing_length before using causally.",
    }


def summarize_ict(st: pd.DataFrame) -> dict:
    return {
        "swings": int((st["swing_type"] != "").sum()),
        "hh": int((st["structure_label"] == "HH").sum()),
        "hl": int((st["structure_label"] == "HL").sum()),
        "lh": int((st["structure_label"] == "LH").sum()),
        "ll": int((st["structure_label"] == "LL").sum()),
        "bullish_bos": int(st["bullish_bos"].sum()),
        "bearish_bos": int(st["bearish_bos"].sum()),
        "bullish_choch": int(st["bullish_choch"].sum()),
        "bearish_choch": int(st["bearish_choch"].sum()),
        "bullish_bars": int((st["ict_state"] == "bullish").sum()),
        "bearish_bars": int((st["ict_state"] == "bearish").sum()),
        "transition_bars": int(st["ict_state"].str.startswith("transition").sum()),
        "neutral_bars": int((st["ict_state"] == "neutral").sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit strict ICT structure.")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--tf", default="5")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--left", type=int, default=3)
    parser.add_argument("--right", type=int, default=3)
    parser.add_argument("--events", type=int, default=40)
    args = parser.parse_args()

    symbol = args.symbol.upper()
    df = load_data(symbol, args.tf, days=args.days, asset_type=asset_type_for(symbol))
    if df.empty:
        raise SystemExit(f"No data loaded for {symbol} {args.tf}")

    st = build_ict_structure_index(df, IctStructureConfig(left=args.left, right=args.right))
    print(f"{symbol} {args.tf}m rows={len(df)} days={args.days} left={args.left} right={args.right}")
    print("\nOUR STRICT ICT:")
    print(pd.Series(summarize_ict(st)).to_string())
    print("\nSMARTMONEYCONCEPTS REFERENCE:")
    print(pd.Series(smc_summary(df, args.left)).to_string())

    mask = (
        (st["structure_label"] != "")
        | st["bullish_choch"]
        | st["bearish_choch"]
        | st["bullish_bos"]
        | st["bearish_bos"]
    )
    cols = [
        "ts",
        "structure_label",
        "swing_type",
        "swing_price",
        "ict_state",
        "direction_bias",
        "bearish_choch",
        "bearish_bos",
        "bullish_choch",
        "bullish_bos",
        "choch_level",
        "bos_level",
        "protected_high",
        "protected_low",
    ]
    print("\nRECENT STRUCTURE EVENTS:")
    print(st.loc[mask, cols].tail(args.events).to_string(index=False))


if __name__ == "__main__":
    main()
