#!/usr/bin/env python3
"""Index no-lookahead structure features for exchange-scoped crypto data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.engine.data import load_data
from backtesting.features.structure import StructureConfig, build_structure_index

OUT = ROOT / "data" / "features" / "structure"
DEFAULT_EXCHANGES = ("binance", "bybit")
DEFAULT_TFS = ("1", "3", "5", "15", "30", "60", "240", "1440")


def _symbols(exchange: str) -> list[str]:
    base = ROOT / "data" / "market_data" / "crypto" / exchange
    out = []
    for path in sorted(base.glob("*1.parquet")):
        if path.stem.endswith("_funding"):
            continue
        out.append(path.stem[:-1])
    return out


def _out_path(exchange: str, symbol: str, tf: str, cfg: StructureConfig) -> Path:
    return OUT / f"L{cfg.left}_R{cfg.right}" / exchange / symbol / f"{tf}.parquet"


def index_one(exchange: str, symbol: str, tf: str, cfg: StructureConfig, days: int = 0) -> dict:
    df = load_data(symbol, tf=tf, asset_type="crypto", exchange=exchange, days=days)
    if df.empty:
        return {"exchange": exchange, "symbol": symbol, "tf": tf, "rows": 0, "events": 0, "path": "", "status": "no_data"}

    features = build_structure_index(df, cfg)
    path = _out_path(exchange, symbol, tf, cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(path, index=False)
    events = int((features["structure_label"] != "").sum())
    return {
        "exchange": exchange,
        "symbol": symbol,
        "tf": tf,
        "rows": len(features),
        "events": events,
        "start": str(features["ts"].min()),
        "end": str(features["ts"].max()),
        "path": str(path),
        "status": "ok",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Index crypto HH/HL/LH/LL structure features.")
    parser.add_argument("--exchange", default="both", choices=["binance", "bybit", "both"])
    parser.add_argument("--symbols", default="", help="Comma-separated symbols; default = all found")
    parser.add_argument("--tfs", default=",".join(DEFAULT_TFS))
    parser.add_argument("--left", type=int, default=2)
    parser.add_argument("--right", type=int, default=2)
    parser.add_argument("--days", type=int, default=0, help="Optional recent-day slice")
    parser.add_argument("--summary-csv", default="", help="Optional CSV path for coverage summary")
    args = parser.parse_args()

    cfg = StructureConfig(left=args.left, right=args.right)
    exchanges = list(DEFAULT_EXCHANGES) if args.exchange == "both" else [args.exchange]
    tfs = [tf.strip() for tf in args.tfs.split(",") if tf.strip()]
    rows = []

    for exchange in exchanges:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or _symbols(exchange)
        for symbol in symbols:
            for tf in tfs:
                row = index_one(exchange, symbol, tf, cfg, days=args.days)
                rows.append(row)
                if row["status"] == "ok":
                    print(f"{exchange} {symbol} {tf}: rows={row['rows']} events={row['events']}")
                else:
                    print(f"{exchange} {symbol} {tf}: {row['status']}")

    summary = pd.DataFrame(rows)
    if args.summary_csv:
        out = Path(args.summary_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(out, index=False)
        print(f"Saved {out} rows={len(summary)}")


if __name__ == "__main__":
    main()
