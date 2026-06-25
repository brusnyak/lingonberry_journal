#!/usr/bin/env python3
"""Quick connectivity + schema test for TradeLocker.

Usage:
  cd backend
  ./venv/bin/python scripts/test_tradelocker_connection.py --symbol GBPUSD --timeframe 5m --limit 50
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.tradelocker_source import TradeLockerSource



def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--timeframe", required=True)
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    src = TradeLockerSource()
    ok = src.is_available()
    if not ok:
        print("TradeLocker auth failed (continue with fetch attempts)")


    # since ~1 day ago for warm-up
    since = datetime.now(tz=timezone.utc) - timedelta(days=3)
    df = src.fetch_ohlcv(symbol=args.symbol, timeframe=args.timeframe, limit=args.limit, since=since)

    if df.empty:
        raise SystemExit("No candles returned")

    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns: {missing}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise SystemExit("Index is not DatetimeIndex")

    print("OK")
    print({"rows": len(df), "start": df.index.min().isoformat(), "end": df.index.max().isoformat()})


if __name__ == "__main__":
    main()

