#!/usr/bin/env python3
"""Print coverage for exchange-scoped crypto parquet data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = ROOT / "data" / "market_data" / "crypto"
TFS = ["1", "3", "5", "15", "60", "240", "1440"]


def coverage(exchange: str, symbol: str) -> dict:
    row = {"exchange": exchange, "symbol": symbol}
    exdir = BASE / exchange
    for tf in TFS:
        path = exdir / f"{symbol}{tf}.parquet"
        if not path.exists():
            row[f"{tf}_bars"] = 0
            row[f"{tf}_start"] = ""
            row[f"{tf}_end"] = ""
            continue
        df = pd.read_parquet(path, columns=["ts"])
        ts = pd.to_datetime(df["ts"], utc=True)
        row[f"{tf}_bars"] = len(df)
        row[f"{tf}_start"] = str(ts.min())
        row[f"{tf}_end"] = str(ts.max())

    fpath = exdir / f"{symbol}_funding.parquet"
    if fpath.exists():
        fdf = pd.read_parquet(fpath, columns=["ts"])
        fts = pd.to_datetime(fdf["ts"], utc=True)
        row["funding_rows"] = len(fdf)
        row["funding_start"] = str(fts.min())
        row["funding_end"] = str(fts.max())
    else:
        row["funding_rows"] = 0
        row["funding_start"] = ""
        row["funding_end"] = ""
    return row


def symbols_for(exchange: str) -> list[str]:
    exdir = BASE / exchange
    symbols = []
    for path in sorted(exdir.glob("*1.parquet")):
        if path.stem.endswith("_funding"):
            continue
        symbols.append(path.stem[:-1])
    return symbols


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit crypto parquet coverage.")
    parser.add_argument("--exchange", default="both", choices=["binance", "bybit", "both"])
    parser.add_argument("--symbols", default="", help="Comma-separated symbols; default = all found")
    parser.add_argument("--csv", default="", help="Optional output CSV path")
    args = parser.parse_args()

    exchanges = ["binance", "bybit"] if args.exchange == "both" else [args.exchange]
    rows = []
    for exchange in exchanges:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        if not symbols:
            symbols = symbols_for(exchange)
        for symbol in symbols:
            rows.append(coverage(exchange, symbol))

    df = pd.DataFrame(rows)
    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"Saved {out} rows={len(df)}")

    if df.empty:
        print("No crypto data found.")
        return

    cols = ["exchange", "symbol", "1_bars", "1_start", "1_end", "funding_rows"]
    print(df[cols].to_string(index=False))


if __name__ == "__main__":
    main()
