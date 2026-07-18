"""
Full inventory of crypto market data on disk: per symbol, per timeframe,
merged (legacy + exchange-scoped) date range, row count, and funding-rate
coverage. Answers "what do we actually have to test with" directly from
files on disk rather than trusting stale memory of a prior audit.

Usage: python -m backtesting.crypto.data_inventory
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from backtesting.crypto.data import load_crypto, load_funding_rate

BASE = ROOT / "data" / "market_data" / "crypto"
SOURCES = ("binance", "bybit", "legacy")
TFS = ("1", "5", "15", "30", "60", "240", "1440")


def discover_symbols() -> list[str]:
    symbols = set()
    for src in SOURCES:
        d = BASE / src
        if not d.exists():
            continue
        for f in d.glob("*.parquet"):
            m = re.match(r"^([A-Z0-9]+?)(1440|240|60|30|15|5|3|1)\.parquet$", f.name)
            if m:
                symbols.add(m.group(1))
    return sorted(symbols)


def main():
    symbols = discover_symbols()
    rows = []
    for symbol in symbols:
        funding = load_funding_rate(symbol)  # tries binance, bybit, legacy in order
        fund_start = funding["ts"].min() if not funding.empty else None
        fund_end = funding["ts"].max() if not funding.empty else None

        for tf in TFS:
            df = load_crypto(symbol, tf=tf, source="merged", resample=False)
            if df.empty:
                continue
            span_days = (df["ts"].max() - df["ts"].min()).days
            rows.append({
                "symbol": symbol,
                "tf": tf,
                "rows": len(df),
                "start": df["ts"].min(),
                "end": df["ts"].max(),
                "span_days": span_days,
                "funding_start": fund_start,
                "funding_covers_start": (fund_start is not None and fund_start <= df["ts"].min()),
            })

    out = pd.DataFrame(rows)
    out_path = ROOT / "backtesting" / "crypto" / "reports" / "data_inventory.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"Saved: {out_path} ({len(out)} rows)")

    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 500)
    # Focus view: intraday/scalping-relevant TFs only, sorted by span
    intraday = out[out["tf"].isin(["1", "5", "15", "30"])].sort_values(
        ["tf", "span_days"], ascending=[True, False]
    )
    print("\n=== Intraday TFs (1/5/15/30m), merged legacy+exchange ===")
    print(intraday[["symbol", "tf", "rows", "start", "end", "span_days", "funding_covers_start"]].to_string(index=False))


if __name__ == "__main__":
    main()
